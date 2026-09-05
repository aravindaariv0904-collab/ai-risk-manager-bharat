import pytest
from unittest.mock import MagicMock, patch
from app.payments.post_payment import post_payment_processor
from app.payments.state_machine import TransactionStatus


class TestPostPaymentProcessingPipeline:
    @pytest.mark.asyncio
    async def test_captured_payment_flow(self):
        txn_id = "00000000-0000-0000-0000-000000000050"
        payment_id = "pay_captured_001"
        order_id = "order_captured_001"
        merchant_id = "00000000-0000-0000-0000-000000000051"

        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{
                "id": txn_id,
                "status": TransactionStatus.AUTHORIZED.value,
                "amount": 25000,
                "merchant_id": merchant_id,
            }]
        )
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
            data={"id": merchant_id, "risk_profile": {"total_captured_volume": 100000, "successful_txns_count": 4}}
        )
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock()

        with patch.object(post_payment_processor, "_supabase", mock_supabase):
            result = await post_payment_processor.process_payment_finalization(
                payment_id=payment_id,
                order_id=order_id,
                target_status=TransactionStatus.CAPTURED,
                amount=25000,
            )
            assert result["status"] == "success"
            assert result["previous_status"] == TransactionStatus.AUTHORIZED.value
            assert result["final_status"] == TransactionStatus.CAPTURED.value

    @pytest.mark.asyncio
    async def test_failed_payment_flow(self):
        txn_id = "00000000-0000-0000-0000-000000000060"
        payment_id = "pay_failed_001"
        order_id = "order_failed_001"
        merchant_id = "00000000-0000-0000-0000-000000000061"

        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{
                "id": txn_id,
                "status": TransactionStatus.AUTHORIZED.value,
                "amount": 5000,
                "merchant_id": merchant_id,
            }]
        )
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
            data={"id": merchant_id, "risk_profile": {"failed_txns_count": 1}}
        )
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock()

        with patch.object(post_payment_processor, "_supabase", mock_supabase):
            result = await post_payment_processor.process_payment_finalization(
                payment_id=payment_id,
                order_id=order_id,
                target_status=TransactionStatus.FAILED,
                amount=5000,
                error_details={"error_code": "INSUFFICIENT_FUNDS"},
            )
            assert result["status"] == "success"
            assert result["final_status"] == TransactionStatus.FAILED.value

    @pytest.mark.asyncio
    async def test_duplicate_webhook_already_processed_idempotent(self):
        txn_id = "00000000-0000-0000-0000-000000000070"
        payment_id = "pay_dup_001"

        mock_supabase = MagicMock()
        # Transaction is already in CAPTURED status
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{
                "id": txn_id,
                "status": TransactionStatus.CAPTURED.value,
                "amount": 10000,
            }]
        )

        with patch.object(post_payment_processor, "_supabase", mock_supabase):
            result = await post_payment_processor.process_payment_finalization(
                payment_id=payment_id,
                order_id="order_dup_001",
                target_status=TransactionStatus.CAPTURED,
                amount=10000,
            )
            assert result["status"] == "already_processed"
            assert result["current_status"] == TransactionStatus.CAPTURED.value

    @pytest.mark.asyncio
    async def test_missing_transaction_skips_gracefully(self):
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

        with patch.object(post_payment_processor, "_supabase", mock_supabase):
            result = await post_payment_processor.process_payment_finalization(
                payment_id="pay_non_existent",
                order_id="order_non_existent",
                target_status=TransactionStatus.CAPTURED,
            )
            assert result["status"] == "skipped"
            assert result["reason"] == "transaction_not_found"
