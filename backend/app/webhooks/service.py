import hashlib
import json
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models import Transaction, WebhookEvent, WebhookProcessingStatus, TransactionStatus, Merchant
from app.razorpay.service import razorpay_service
from app.services.database import get_db
from app.services.supabase_client import get_supabase_admin
from app.risk.engine import risk_engine


class WebhookService:
    def __init__(self):
        self._supabase = None

    @property
    def supabase(self):
        if self._supabase is None:
            self._supabase = get_supabase_admin()
        return self._supabase

    async def process_webhook(self, payload: bytes, signature: str) -> Dict[str, Any]:
        if not razorpay_service.verify_webhook_signature(payload, signature):
            return {"error": "Invalid signature", "status": "rejected"}

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON", "status": "rejected"}

        event_id = data.get("id")
        if not event_id:
            return {"error": "Missing event ID", "status": "rejected"}

        existing = self.supabase.table("webhook_events").select("id").eq("event_id", event_id).execute()
        if existing.data:
            return {"status": "duplicate", "event_id": event_id}

        payload_hash = hashlib.sha256(payload).hexdigest()

        self.supabase.table("webhook_events").insert({
            "event_id": event_id,
            "event_type": data.get("event"),
            "payload_hash": payload_hash,
            "processing_status": "pending",
        }).execute()

        try:
            await self._handle_event(data)
            self.supabase.table("webhook_events").update({
                "processing_status": "processed",
                "processed_at": datetime.utcnow().isoformat(),
            }).eq("event_id", event_id).execute()
            return {"status": "processed", "event_id": event_id}
        except Exception as e:
            self.supabase.table("webhook_events").update({
                "processing_status": "failed",
            }).eq("event_id", event_id).execute()
            raise

    async def _handle_event(self, data: Dict[str, Any]):
        event_type = data.get("event")
        parsed = razorpay_service.parse_webhook_payload(data)

        payment_id = parsed.get("payment_id")
        order_id = parsed.get("order_id")
        amount = parsed.get("amount")
        status = parsed.get("status")

        if event_type in ["payment.captured", "payment.failed", "order.paid"]:
            await self._update_transaction(payment_id, order_id, amount, status, parsed)

    async def _update_transaction(self, payment_id: Optional[str], order_id: Optional[str], amount: Optional[int], status: Optional[str], parsed: Dict):
        if not payment_id and not order_id:
            return

        query = self.supabase.table("transactions")
        if payment_id:
            query = query.eq("razorpay_payment_id", payment_id)
        elif order_id:
            query = query.eq("razorpay_order_id", order_id)

        existing = query.execute()
        if not existing.data:
            return

        txn = existing.data[0]
        txn_id = txn["id"]

        status_map = {
            "captured": TransactionStatus.CAPTURED.value,
            "failed": TransactionStatus.FAILED.value,
            "created": TransactionStatus.PENDING.value,
            "authorized": TransactionStatus.PENDING.value,
        }
        new_status = status_map.get(status, TransactionStatus.PENDING.value)

        update_data = {
            "status": new_status,
            "updated_at": datetime.utcnow().isoformat(),
        }
        if payment_id and not txn.get("razorpay_payment_id"):
            update_data["razorpay_payment_id"] = payment_id
        if amount:
            update_data["amount"] = amount

        self.supabase.table("transactions").update(update_data).eq("id", txn_id).execute()

        if new_status == TransactionStatus.CAPTURED.value:
            await self._post_payment_processing(txn_id, txn)

    async def _post_payment_processing(self, txn_id: str, txn: Dict):
        pass


webhook_service = WebhookService()