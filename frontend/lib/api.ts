/**
 * API Client for AutoSQL Backend
 * 
 * Simplified client focused on AI SQL generation and execution
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface AIQueryRequest {
  prompt: string
  session_id?: string
  max_retries?: number
  use_workflow?: boolean
  reset_database?: boolean
}

export interface TableResult {
  columns: string[]
  rows: Array<Record<string, any>>
  row_count: number
  affected_rows: number
  execution_time_ms: number
  query: string
  query_type: string
  table_name?: string
}

export interface AIQueryResponse {
  success: boolean
  prompt: string
  sql?: string
  columns?: string[]
  rows?: Array<Record<string, any>>
  row_count: number
  affected_rows: number
  execution_time_ms: number
  error?: string
  explanation?: string
  metadata: Record<string, any>
  timestamp: string
  // New field for multiple table results
  table_results?: TableResult[]
}

export interface ConversationMessage {
  type: 'user' | 'assistant' | 'system' | 'error'
  content: string
  timestamp: string
  sql_query?: string
  execution_result?: Record<string, any>
  metadata?: Record<string, any>
}

export interface ConversationHistory {
  messages: ConversationMessage[]
  session_id: string
  total_count: number
}

export interface EnhanceSQLRequest {
  prompt: string
  current_sql?: string
}

export interface QuickSQLResponse {
  success: boolean
  prompt: string
  sql?: string
  error?: string
  metadata: Record<string, any>
  timestamp: string
}

export interface ExecuteQueryRequest {
  sql: string
  parameters?: Record<string, any>
  save_to_history?: boolean
  auto_commit?: boolean
  safety_check?: boolean
  session_id?: string
}

export interface ExecuteQueryResponse {
  success: boolean
  query: string
  execution_time_ms: number
  rows: Array<Record<string, any>>
  columns: string[]
  row_count: number
  affected_rows: number
  error_message?: string
  error_type?: string
  metadata: Record<string, any>
  timestamp: string
  table_results?: TableResult[]
}

class APIClient {
  private baseUrl: string

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`
    
    const config: RequestInit = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    }

    try {
      const response = await fetch(url, config)
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }))
        throw new Error(errorData.detail || errorData.error || `HTTP ${response.status}`)
      }

      return await response.json()
    } catch (error) {
      console.error(`API request failed: ${endpoint}`, error)
      throw error
    }
  }

  // Health check endpoints
  async ping(): Promise<{ message: string }> {
    return this.request('/ping')
  }

  async health(): Promise<{ status: string; [key: string]: any }> {
    return this.request('/health')
  }

  // AI endpoints - main functionality
  async generateQuery(request: AIQueryRequest): Promise<AIQueryResponse> {
    return this.request('/api/ai/query', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  async explainQuery(sql: string): Promise<{ explanation: string }> {
    return this.request('/api/ai/explain', {
      method: 'POST',
      body: JSON.stringify({ sql }),
    })
  }

  // Database execution endpoints
  async executeQuery(request: ExecuteQueryRequest): Promise<ExecuteQueryResponse> {
    return this.request('/api/db/execute', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  // Conversation management
  async getConversationHistory(sessionId: string, limit = 10): Promise<ConversationHistory> {
    return this.request(`/api/ai/conversation/${sessionId}?limit=${limit}`)
  }

  async clearConversation(sessionId: string): Promise<{ success: boolean; message: string }> {
    return this.request(`/api/ai/conversation/${sessionId}`, {
      method: 'DELETE',
    })
  }

  // Context-aware code enhancement
  async enhanceCode(request: EnhanceSQLRequest): Promise<QuickSQLResponse> {
    return this.request('/api/ai/enhance-code', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }
}

// Create and export a singleton instance
export const apiClient = new APIClient()

// Export wrapper functions for clean usage
export const ping = () => apiClient.ping()
export const health = () => apiClient.health()
export const generateQuery = (request: AIQueryRequest) => apiClient.generateQuery(request)
export const explainQuery = (sql: string) => apiClient.explainQuery(sql)
export const executeQuery = (request: ExecuteQueryRequest) => apiClient.executeQuery(request)
export const getConversationHistory = (sessionId: string, limit?: number) => apiClient.getConversationHistory(sessionId, limit)
export const clearConversation = (sessionId: string) => apiClient.clearConversation(sessionId)
export const enhanceCode = (request: EnhanceSQLRequest) => apiClient.enhanceCode(request)
