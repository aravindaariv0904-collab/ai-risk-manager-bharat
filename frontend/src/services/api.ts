import { supabase } from './supabase'
import { getDemoSession } from './demoSession'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

class ApiClient {
  private async getAccessToken(): Promise<string | null> {
    const demo = getDemoSession()
    if (demo?.token) return demo.token

    try {
      const { data } = await supabase.auth.getSession()
      return data.session?.access_token ?? null
    } catch {
      return null
    }
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const token = await this.getAccessToken()

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    }

    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    const url = API_BASE_URL ? `${API_BASE_URL}${path}` : path

    let response: Response
    try {
      response = await fetch(url, {
        ...options,
        headers,
      })
    } catch (err: any) {
      throw new Error(err.message || 'Unable to connect to Risk Engine API server')
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => null)
      throw new Error(errorData?.detail || `Request failed: ${response.status}`)
    }

    return response.json() as Promise<T>
  }

  get<T>(path: string): Promise<T> {
    return this.request<T>(path)
  }

  post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    })
  }
}

export const api = new ApiClient()