import React from 'react'
import ReactDOM from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import './index.css'

import App from './App'
import AuthPage from './pages/AuthPage'
import CitizenDashboard from './pages/CitizenDashboard'
import PaymentRiskPage from './pages/PaymentRiskPage'
import TransactionsPage from './pages/TransactionsPage'
import AssistantPage from './pages/AssistantPage'
import VendorDashboard from './pages/VendorDashboard'
import VendorVerification from './pages/VendorVerification'
import VendorTransactions from './pages/VendorTransactions'
import AdminDashboard from './pages/AdminDashboard'
import SettingsPage from './pages/SettingsPage'
import ProtectedRoute from './components/ProtectedRoute'

const router = createBrowserRouter([
  {
    path: '/auth',
    element: <AuthPage />,
  },
  {
    path: '/',
    element: <App />,
    children: [
      { index: true, element: <ProtectedRoute><CitizenDashboard /></ProtectedRoute> },
      { path: 'pay', element: <ProtectedRoute><PaymentRiskPage /></ProtectedRoute> },
      { path: 'history', element: <ProtectedRoute><TransactionsPage /></ProtectedRoute> },
      { path: 'assistant', element: <ProtectedRoute><AssistantPage /></ProtectedRoute> },
      { path: 'vendor', element: <ProtectedRoute><VendorDashboard /></ProtectedRoute> },
      { path: 'vendor/verify', element: <ProtectedRoute><VendorVerification /></ProtectedRoute> },
      { path: 'vendor/transactions', element: <ProtectedRoute><VendorTransactions /></ProtectedRoute> },
      { path: 'admin', element: <ProtectedRoute><AdminDashboard /></ProtectedRoute> },
      { path: 'settings', element: <ProtectedRoute><SettingsPage /></ProtectedRoute> },
    ],
  },
])

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
)