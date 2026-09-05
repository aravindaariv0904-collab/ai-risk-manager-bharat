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
        """Route event to appropriate domain handlers."""
        event_type = data.get("event")
        payment_id = parsed.get("payment_id")
        order_id = parsed.get("order_id")
        amount = parsed.get("amount")

        if event_type == "payment.captured":
            await self._update_transaction_status(
                payment_id=payment_id,
                order_id=order_id,
                amount=amount,
                target_status=TransactionStatus.CAPTURED,
                trigger_post_processing=True,
            )

        elif event_type == "payment.failed":
            await self._update_transaction_status(
                payment_id=payment_id,
                order_id=order_id,
                amount=amount,
                target_status=TransactionStatus.FAILED,
                trigger_post_processing=False,
            )

        elif event_type == "payment.authorized":
            await self._update_transaction_status(
                payment_id=payment_id,
                order_id=order_id,
                amount=amount,
                target_status=TransactionStatus.AUTHORIZED,
                trigger_post_processing=False,
            )

        elif event_type == "order.paid":
            # Order paid guarantees payment capture; update status if not already captured
            await self._update_transaction_status(
                payment_id=payment_id,
                order_id=order_id,
                amount=amount,
                target_status=TransactionStatus.CAPTURED,
                trigger_post_processing=True,
            )

        elif event_type in ["refund.processed", "refund.created"]:
            await self._update_transaction_status(
                payment_id=payment_id,
                order_id=order_id,
                amount=amount,
                target_status=TransactionStatus.REFUNDED,
                trigger_post_processing=False,
            )

        else:
            logger.info("Received unsupported or informational webhook event", event_type=event_type)

    async def _update_transaction_status(
        self,
        payment_id: Optional[str],
        order_id: Optional[str],
        amount: Optional[int],
        target_status: TransactionStatus,
        trigger_post_processing: bool = False,
    ):
        """Update transaction status using validated state transitions."""
        if not payment_id and not order_id:
            logger.warning("Cannot update transaction: missing both payment_id and order_id")
            return

        query = self.supabase.table("transactions").select("*")
        if payment_id:
            query = query.eq("razorpay_payment_id", payment_id)
        elif order_id:
            query = query.eq("razorpay_order_id", order_id)

        res = query.execute()
        if not res.data:
            logger.info("No existing transaction matched for webhook", payment_id=payment_id, order_id=order_id)
            return

        txn = res.data[0]
        txn_id = txn["id"]
        current_status = normalize_transaction_status(txn.get("status"))

        # Execute validated state transition
        next_status = transition_transaction(current_status, target_status, strict=False)

        update_payload: Dict[str, Any] = {
            "status": next_status.value,
            "updated_at": datetime.utcnow().isoformat(),
        }

        if payment_id and not txn.get("razorpay_payment_id"):
            update_payload["razorpay_payment_id"] = payment_id
        if amount and not txn.get("amount"):
            update_payload["amount"] = amount

        self.supabase.table("transactions").update(update_payload).eq("id", txn_id).execute()
        logger.info(
            "Transaction status updated via webhook",
            transaction_id=txn_id,
            from_status=current_status.value,
            to_status=next_status.value,
        )

        # Execute post-payment side effects only once upon first capture
        if trigger_post_processing and next_status == TransactionStatus.CAPTURED and current_status != TransactionStatus.CAPTURED:
            await self._post_payment_processing(txn_id, txn, amount)

    async def _post_payment_processing(self, txn_id: str, txn: Dict, amount: Optional[int]):
        """Execute audit logging and merchant profile update upon payment capture."""
        try:
            merchant_id = txn.get("merchant_id")
            if not merchant_id:
                return

            m_resp = self.supabase.table("merchants").select("risk_profile").eq("id", merchant_id).maybe_single().execute()
            if m_resp and m_resp.data:
                profile = m_resp.data.get("risk_profile") or {}
                captured_amount = amount or txn.get("amount") or 0
                total_captured = profile.get("total_captured_volume", 0) + captured_amount
                profile["total_captured_volume"] = total_captured
                profile["last_payment_at"] = datetime.utcnow().isoformat()
                self.supabase.table("merchants").update({"risk_profile": profile}).eq("id", merchant_id).execute()
                logger.info("Merchant profile volume updated after capture", merchant_id=merchant_id, total_captured=total_captured)
        except Exception as e:
            logger.warning("Post-payment merchant profile update warning", error=str(e), transaction_id=txn_id)


webhook_service = WebhookService()