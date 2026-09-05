import hashlib
import json
from datetime import datetime
from typing import Dict, Any, Optional
import structlog

from app.models import WebhookProcessingStatus
from app.payments.state_machine import (
    TransactionStatus,
    transition_transaction,
    normalize_transaction_status,
)
from app.razorpay.service import razorpay_service
from app.services.supabase_client import get_supabase_admin

logger = structlog.get_logger()


class WebhookService:
    def __init__(self):
        self._supabase = None

    @property
    def supabase(self):
        if self._supabase is None:
            self._supabase = get_supabase_admin()
        return self._supabase

    async def process_webhook(
        self,
        payload: bytes,
        signature: Optional[str],
        event_id_header: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ingest, verify, idempotently record, and process a Razorpay webhook event.
        Guarantees signature verification before parsing, atomic duplicate prevention,
        and safe retryability.
        """
        # 1. Verify webhook signature BEFORE processing
        if not signature or not razorpay_service.verify_webhook_signature(payload, signature):
            logger.warning("Rejected webhook due to missing or invalid signature")
            return {"error": "Invalid or missing webhook signature", "status": "rejected"}

        # 2. Parse & validate JSON payload
        try:
            data = json.loads(payload)
            if not isinstance(data, dict):
                return {"error": "Malformed webhook payload: root is not a JSON object", "status": "rejected"}
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning("Malformed JSON in webhook body", error=str(e))
            return {"error": f"Invalid JSON payload: {str(e)}", "status": "rejected"}

        # 3. Extract official event ID (from X-Razorpay-Event-Id header or payload)
        event_id = event_id_header or data.get("id") or data.get("event_id")
        if not event_id:
            logger.warning("Missing event ID in webhook request")
            return {"error": "Missing event ID in headers or payload", "status": "rejected"}

        event_type = data.get("event", "unknown")
        payload_hash = hashlib.sha256(payload).hexdigest()

        # Parse entity fields
        parsed = razorpay_service.parse_webhook_payload(data)
        payment_id = parsed.get("payment_id")
        order_id = parsed.get("order_id")

        # 4. Atomic Idempotency Check & Record Creation
        # Check if event already exists in webhook_events
        existing_event = None
        try:
            res = self.supabase.table("webhook_events").select("*").eq("event_id", event_id).maybe_single().execute()
            existing_event = res.data if res else None
        except Exception as e:
            logger.warning("Failed to query existing webhook event", error=str(e), event_id=event_id)

        if existing_event:
            status = existing_event.get("processing_status")
            if status == "processed":
                logger.info("Ignoring duplicate webhook event (already processed)", event_id=event_id)
                return {"status": "duplicate", "event_id": event_id, "message": "Event already processed"}
            elif status == "pending":
                logger.info("Ignoring duplicate concurrent webhook event (in progress)", event_id=event_id)
                return {"status": "duplicate", "event_id": event_id, "message": "Event currently processing"}
            # If status == 'failed', we allow retry processing below
            logger.info("Retrying previously failed webhook event", event_id=event_id)
        else:
            # Atomic insertion into webhook_events
            try:
                self.supabase.table("webhook_events").insert({
                    "event_id": event_id,
                    "event_type": event_type,
                    "payload_hash": payload_hash,
                    "payment_id": payment_id,
                    "order_id": order_id,
                    "processing_status": "pending",
                }).execute()
            except Exception as e:
                # Concurrent race condition caught by UNIQUE constraint on event_id
                logger.warning("Caught concurrent duplicate webhook insertion", event_id=event_id, error=str(e))
                return {"status": "duplicate", "event_id": event_id, "message": "Duplicate event received"}

        # 5. Execute Event Handling
        try:
            await self._handle_event(data, parsed)

            # Mark as processed successfully
            try:
                self.supabase.table("webhook_events").update({
                    "processing_status": "processed",
                    "processing_error": None,
                    "processed_at": datetime.utcnow().isoformat(),
                }).eq("event_id", event_id).execute()
            except Exception as e:
                logger.warning("Failed to update webhook event to processed", error=str(e))

            logger.info("Webhook event processed successfully", event_id=event_id, event_type=event_type)
            return {"status": "processed", "event_id": event_id, "event_type": event_type}

        except Exception as e:
            err_msg = str(e)
            logger.error("Error processing webhook event", event_id=event_id, error=err_msg)
            try:
                self.supabase.table("webhook_events").update({
                    "processing_status": "failed",
                    "processing_error": err_msg,
                }).eq("event_id", event_id).execute()
            except Exception:
                pass
            raise

    async def _handle_event(self, data: Dict[str, Any], parsed: Dict[str, Any]):
        """Route event to appropriate domain handlers and post-payment pipeline."""
        from app.payments.post_payment import post_payment_processor

        event_type = data.get("event")
        payment_id = parsed.get("payment_id")
        order_id = parsed.get("order_id")
        amount = parsed.get("amount")

        if event_type == "payment.captured":
            await post_payment_processor.process_payment_finalization(
                payment_id=payment_id,
                order_id=order_id,
                target_status=TransactionStatus.CAPTURED,
                amount=amount,
                actor="WEBHOOK:payment.captured",
            )

        elif event_type == "payment.failed":
            await post_payment_processor.process_payment_finalization(
                payment_id=payment_id,
                order_id=order_id,
                target_status=TransactionStatus.FAILED,
                amount=amount,
                error_details={"error_code": parsed.get("error_code"), "error_description": parsed.get("error_description")},
                actor="WEBHOOK:payment.failed",
            )

        elif event_type == "payment.authorized":
            await post_payment_processor.process_payment_finalization(
                payment_id=payment_id,
                order_id=order_id,
                target_status=TransactionStatus.AUTHORIZED,
                amount=amount,
                actor="WEBHOOK:payment.authorized",
            )

        elif event_type == "order.paid":
            await post_payment_processor.process_payment_finalization(
                payment_id=payment_id,
                order_id=order_id,
                target_status=TransactionStatus.CAPTURED,
                amount=amount,
                actor="WEBHOOK:order.paid",
            )

        elif event_type in ["refund.processed", "refund.created"]:
            await post_payment_processor.process_payment_finalization(
                payment_id=payment_id,
                order_id=order_id,
                target_status=TransactionStatus.REFUNDED,
                amount=amount,
                actor=f"WEBHOOK:{event_type}",
            )

        else:
            logger.info("Received unsupported or informational webhook event", event_type=event_type)


webhook_service = WebhookService()