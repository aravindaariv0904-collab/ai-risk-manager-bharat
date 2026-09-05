import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import RiskResultCard, { formatSignalName } from '../RiskResultCard'
import type { RiskPrecheckResult } from '../../types'

describe('RiskResultCard Component', () => {
  const mockLowResult: RiskPrecheckResult = {
    transaction_id: 'txn-low-123',
    risk_score: 15,
    risk_level: 'LOW',
    risk_action: 'ALLOW',
    reasons: [],
    recommended_action: 'Safe to proceed with payment. Verified within standard baseline.',
    human_explanation: 'Transaction passed all baseline verification checks.',
  }

  const mockMediumResult: RiskPrecheckResult = {
    transaction_id: 'txn-med-456',
    risk_score: 45,
    risk_level: 'MEDIUM',
    risk_action: 'STEP_UP_VERIFICATION',
    reasons: [
      {
        signal_name: 'id_new_recipient',
        reason: 'First time transferring to this recipient UPI ID.',
        severity: 'MEDIUM',
        score_impact: 15,
      },
      {
        signal_name: 'txn_amount_spike_3x',
        reason: 'Amount is 3.5x higher than 30-day baseline average.',
        severity: 'MEDIUM',
        score_impact: 18,
      },
    ],
    recommended_action: 'Perform step-up verification (OTP/recipient confirm) before continuing.',
    human_explanation: 'Recipient is new and amount is elevated.',
  }

  const mockHighResult: RiskPrecheckResult = {
    transaction_id: 'txn-high-789',
    risk_score: 75,
    risk_level: 'HIGH',
    risk_action: 'HOLD_FOR_REVIEW',
    reasons: [
      {
        signal_name: 'vel_rapid_txns_1h',
        reason: '5 transactions detected in the past 60 minutes.',
        severity: 'HIGH',
        score_impact: 25,
      },
      {
        signal_name: 'id_unverified_recipient',
        reason: 'Recipient account has unverified identity credentials.',
        severity: 'HIGH',
        score_impact: 20,
      },
    ],
    recommended_action: 'Hold transaction for manual compliance and safety review.',
    human_explanation: 'Velocity spike and unverified counterparty detected.',
  }

  const mockCriticalResult: RiskPrecheckResult = {
    transaction_id: 'txn-crit-999',
    risk_score: 84,
    risk_level: 'CRITICAL',
    risk_action: 'BLOCK',
    reasons: [
      {
        signal_name: 'txn_amount_spike_3x',
        reason: 'Transaction amount is 8x the daily baseline.',
        severity: 'HIGH',
        score_impact: 18,
      },
      {
        signal_name: 'id_new_recipient',
        reason: 'Brand new unverified recipient.',
        severity: 'MEDIUM',
        score_impact: 15,
      },
      {
        signal_name: 'vel_rapid_txns_1h',
        reason: 'Extremely high transaction frequency in 1 hour.',
        severity: 'HIGH',
        score_impact: 20,
      },
      {
        signal_name: 'beh_unusual_hour',
        reason: 'Payment initiated at 03:45 AM outside active history.',
        severity: 'LOW',
        score_impact: 10,
      },
      {
        signal_name: 'ml_isolation_forest_anomaly',
        reason: 'Isolation Forest ML ensemble flagged multidimensional outlier.',
        severity: 'LOW',
        score_impact: 9,
      },
    ],
    recommended_action: 'Do not complete the payment. Review the transaction.',
    human_explanation: 'Severe composite risk detected across multiple dimensions.',
  }

  // 1. Loading State Test
  it('renders loading state when isLoading is true', () => {
    render(<RiskResultCard isLoading={true} />)
    expect(screen.getByRole('region', { name: /Risk Evaluation Loading/i })).toBeInTheDocument()
  })

  // 2. Error State Test with retry & cancel callbacks
  it('renders error state and triggers onRetry and onCancel callbacks', async () => {
    const user = userEvent.setup()
    const handleRetry = vi.fn()
    const handleCancel = vi.fn()

    render(
      <RiskResultCard
        error="Network timeout connecting to risk service"
        onRetry={handleRetry}
        onCancel={handleCancel}
      />
    )

    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByText('Risk Assessment Failed')).toBeInTheDocument()
    expect(screen.getByText('Network timeout connecting to risk service')).toBeInTheDocument()

    const retryBtn = screen.getByRole('button', { name: /Retry Analysis/i })
    const cancelBtn = screen.getByRole('button', { name: /Cancel/i })

    await user.click(retryBtn)
    expect(handleRetry).toHaveBeenCalledTimes(1)

    await user.click(cancelBtn)
    expect(handleCancel).toHaveBeenCalledTimes(1)
  })

  // 3. Empty State Test
  it('renders empty placeholder when result is null', () => {
    render(<RiskResultCard result={null} />)
    expect(screen.getByText('No Risk Analysis Available')).toBeInTheDocument()
    expect(screen.getByText(/Enter recipient details and amount above/i)).toBeInTheDocument()
  })

  // 4. LOW Risk Level Test
  it('renders LOW risk details correctly with ALLOW decision', async () => {
    const user = userEvent.setup()
    const handleContinue = vi.fn()

    render(<RiskResultCard result={mockLowResult} onContinue={handleContinue} />)

    // Score & Badge
    expect(screen.getByTestId('risk-score-value')).toHaveTextContent('15')
    expect(screen.getByTestId('risk-level-badge')).toHaveTextContent('LOW RISK')

    // Decision
    expect(screen.getByTestId('risk-decision-banner')).toHaveTextContent('ALLOW PAYMENT')

    // Recommended Action
    expect(screen.getByTestId('recommended-action-text')).toHaveTextContent(
      'Safe to proceed with payment. Verified within standard baseline.'
    )

    // Missing / Empty signals display
    expect(screen.getByTestId('empty-signals-state')).toBeInTheDocument()
    expect(screen.getByText('No risk signals detected')).toBeInTheDocument()

    // Action button enabled
    const continueBtn = screen.getByRole('button', { name: /Continue Payment/i })
    expect(continueBtn).toBeEnabled()
    await user.click(continueBtn)
    expect(handleContinue).toHaveBeenCalledTimes(1)
  })

  // 5. MEDIUM Risk Level Test
  it('renders MEDIUM risk details correctly with STEP-UP VERIFICATION decision', () => {
    render(<RiskResultCard result={mockMediumResult} />)

    expect(screen.getByTestId('risk-score-value')).toHaveTextContent('45')
    expect(screen.getByTestId('risk-level-badge')).toHaveTextContent('MEDIUM RISK')
    expect(screen.getByTestId('risk-decision-banner')).toHaveTextContent('STEP-UP VERIFICATION')
    expect(screen.getByTestId('recommended-action-text')).toHaveTextContent(
      'Perform step-up verification (OTP/recipient confirm) before continuing.'
    )

    expect(screen.getByRole('button', { name: /Verify Recipient & Proceed/i })).toBeEnabled()
  })

  // 6. HIGH Risk Level Test
  it('renders HIGH risk details correctly with HOLD FOR REVIEW decision', () => {
    render(<RiskResultCard result={mockHighResult} />)

    expect(screen.getByTestId('risk-score-value')).toHaveTextContent('75')
    expect(screen.getByTestId('risk-level-badge')).toHaveTextContent('HIGH RISK')
    expect(screen.getByTestId('risk-decision-banner')).toHaveTextContent('HOLD FOR REVIEW')
    expect(screen.getByTestId('recommended-action-text')).toHaveTextContent(
      'Hold transaction for manual compliance and safety review.'
    )

    expect(screen.getByRole('button', { name: /Submit for Manual Review/i })).toBeEnabled()
  })

  // 7. CRITICAL Risk Level Test (Score 84, BLOCK PAYMENT, Signal Breakdown, Button Disabled)
  it('renders CRITICAL risk details with 84 / 100, BLOCK PAYMENT, and structured signals breakdown', () => {
    render(<RiskResultCard result={mockCriticalResult} />)

    // Header
    expect(screen.getByText('RISK SCORE')).toBeInTheDocument()
    expect(screen.getByTestId('risk-score-value')).toHaveTextContent('84')
    expect(screen.getByText('/ 100')).toBeInTheDocument()
    expect(screen.getByTestId('risk-level-badge')).toHaveTextContent('CRITICAL RISK')

    // Decision & Recommended Action
    expect(screen.getByTestId('risk-decision-banner')).toHaveTextContent('BLOCK PAYMENT')
    expect(screen.getByTestId('recommended-action-text')).toHaveTextContent(
      'Do not complete the payment. Review the transaction.'
    )

    // WHY THIS PAYMENT WAS FLAGGED Section
    expect(screen.getByText('WHY THIS PAYMENT WAS FLAGGED')).toBeInTheDocument()
    expect(screen.getByText('5 signals')).toBeInTheDocument()

    // Individual Signal Rows & Score Contributions
    expect(screen.getByText('Unusual transaction amount')).toBeInTheDocument()
    expect(screen.getByText('Transaction amount is 8x the daily baseline.')).toBeInTheDocument()
    expect(screen.getByText('+18')).toBeInTheDocument()

    expect(screen.getByText('New recipient')).toBeInTheDocument()
    expect(screen.getByText('Brand new unverified recipient.')).toBeInTheDocument()
    expect(screen.getByText('+15')).toBeInTheDocument()

    expect(screen.getByText('High transaction velocity (1h)')).toBeInTheDocument()
    expect(screen.getByText('+20')).toBeInTheDocument()

    expect(screen.getByText('Unusual transaction hour')).toBeInTheDocument()
    expect(screen.getByText('+10')).toBeInTheDocument()

    expect(screen.getByText('ML multidimensional anomaly')).toBeInTheDocument()
    expect(screen.getByText('+9')).toBeInTheDocument()

    // Total Row
    expect(screen.getByText('Total Risk Score')).toBeInTheDocument()

    // Action button disabled
    const blockedBtn = screen.getByRole('button', { name: /Transaction Blocked/i })
    expect(blockedBtn).toBeDisabled()
  })

  // 8. Helper Unit Test: formatSignalName
  it('correctly maps known signals and formats unknown snake_case signals', () => {
    expect(formatSignalName('txn_amount_spike_3x')).toBe('Unusual transaction amount')
    expect(formatSignalName('id_new_recipient')).toBe('New recipient')
    expect(formatSignalName('vel_rapid_txns_1h')).toBe('High transaction velocity (1h)')
    expect(formatSignalName('beh_unusual_hour')).toBe('Unusual transaction hour')
    expect(formatSignalName('ml_isolation_forest_anomaly')).toBe('ML multidimensional anomaly')
    // Fallback snake_case formatting
    expect(formatSignalName('id_suspicious_device')).toBe('Suspicious Device')
    expect(formatSignalName('custom_unusual_location')).toBe('Custom Unusual Location')
  })
})
