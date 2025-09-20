"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useRouter } from "next/navigation"
import { 
  Sparkles, 
  Database, 
  Code2, 
  MessageSquare, 
  Table,
  Play,
  History,
  Settings,
  Home,
  GitBranch
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { AiPromptInterface } from "@/components/ai-prompt-interface"
import { SqlCodeEditor } from "./sql-code-editor"
import { QueryExecutionResults } from "@/components/query-execution-results"
import { executeQuery, generateQuery, clearConversation } from "@/lib/api"
import type { AIQueryResponse, ExecuteQueryResponse, EnhanceSQLRequest, TableResult } from "@/lib/api"

interface Message {
  id: string
  type: 'user' | 'assistant'
  content: string
  timestamp: Date
  execution_result?: ExecuteQueryResponse
}

interface TableTab {
  id: string
  title: string
  tableResult: TableResult
}

export function SqlIdeLayout() {
  const router = useRouter()
  const [hasQuery, setHasQuery] = useState(false)
  const [generatedQuery, setGeneratedQuery] = useState("")
  const [queryResults, setQueryResults] = useState<ExecuteQueryResponse | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [activeTab, setActiveTab] = useState("code")
  const [sessionId] = useState(`session_${Date.now()}`)
  const [isExecuting, setIsExecuting] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [tableTabs, setTableTabs] = useState<TableTab[]>([])

  const handleOpenTableInNewTab = (tableResult: any) => {
    const tabId = `table-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    const newTab: TableTab = {
      id: tabId,
      title: tableResult.table_name || `Table ${tableTabs.length + 1}`,
      tableResult
    }
    setTableTabs(prev => [...prev, newTab])
    setActiveTab(tabId)
  }

  const handleCloseTableTab = (tabId: string) => {
    setTableTabs(prev => prev.filter(tab => tab.id !== tabId))
    // If closing active tab, switch to Results tab
    if (activeTab === tabId) {
      setActiveTab("table")
    }
  }

  const handleQueryGenerated = (query: string) => {
    setGeneratedQuery(query)
    setHasQuery(true)
    
    // Add to conversation - simpler message without showing SQL
    const newMessage: Message = {
      id: Date.now().toString(),
      type: 'assistant',
      content: 'I\'ve generated the SQL query for you. You can review and edit it in the code editor, then execute it.',
      timestamp: new Date()
    }
    setMessages(prev => [...prev, newMessage])
  }

  const handleQueryExecutedFromAI = (result: AIQueryResponse) => {
    // Convert AIQueryResponse to ExecuteQueryResponse format
    const executeResult: ExecuteQueryResponse = {
      success: result.success,
      query: result.sql || '',
      execution_time_ms: result.execution_time_ms,
      rows: result.rows || [],
      columns: result.columns || [],
      row_count: result.row_count,
      affected_rows: result.affected_rows,
      error_message: result.error,
      metadata: result.metadata,
      timestamp: result.timestamp
    }
    
    setQueryResults(executeResult)
    setActiveTab("table")
    
    // Only add error messages to conversation, not success messages
    if (!result.success && result.error) {
      const resultMessage: Message = {
        id: Date.now().toString(),
        type: 'assistant',
        content: `Query failed: ${result.error}`,
        timestamp: new Date(),
        execution_result: executeResult
      }
      setMessages(prev => [...prev, resultMessage])
    }
  }

  const handleDirectExecution = async (sql: string) => {
    setIsExecuting(true)
    try {
      // Clear conversation memory before each execution to prevent issues
      await clearConversation(sessionId)
      
      const result = await executeQuery({
        sql,
        session_id: sessionId,
        save_to_history: true
      })
      
      setQueryResults(result)
      setActiveTab("table")
      
      // Only add error messages to conversation, not success messages
      if (!result.success && result.error_message) {
        const errorMessage: Message = {
          id: Date.now().toString(),
          type: 'assistant',
          content: `Query failed: ${result.error_message}`,
          timestamp: new Date(),
          execution_result: result
        }
        setMessages(prev => [...prev, errorMessage])
      }
      
      // Update the generated query if it was modified
      setGeneratedQuery(sql)
      
    } catch (error) {
      console.error('Query execution failed:', error)
      const errorResult: ExecuteQueryResponse = {
        success: false,
        query: sql,
        execution_time_ms: 0,
        rows: [],
        columns: [],
        row_count: 0,
        affected_rows: 0,
        error_message: error instanceof Error ? error.message : 'Unknown error',
        metadata: {},
        timestamp: new Date().toISOString()
      }
      
      setQueryResults(errorResult)
      setActiveTab("table")
      
      const errorMessage: Message = {
        id: Date.now().toString(),
        type: 'assistant',
        content: `Query failed: ${errorResult.error_message}`,
        timestamp: new Date(),
        execution_result: errorResult
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsExecuting(false)
    }
  }

  const handleNewQuery = (prompt: string) => {
    // Add user message to conversation
    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: prompt,
      timestamp: new Date()
    }
    setMessages(prev => [...prev, userMessage])
  }

  const handleClearConversation = async () => {
    try {
      await clearConversation(sessionId)
      setMessages([])
      setHasQuery(false)
      setGeneratedQuery("")
      setQueryResults(null)
    } catch (error) {
      console.error('Failed to clear conversation:', error)
    }
  }

  return (
    <div className="h-screen flex bg-background overflow-hidden">
      {/* Sidebar - 20% width */}
      <div className="w-1/7 bg-card border-r border-border flex flex-col">
        {/* Brand Header */}
        <div className="p-6 border-b border-border">
          <div className="flex items-center space-x-3">
            <div className="flex items-center justify-center w-10 h-10 bg-primary/10 rounded-lg">
              <Sparkles className="h-6 w-6 text-primary" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-foreground">AutoSQL</h1>
              <p className="text-sm text-muted-foreground">AI SQL Assistant</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4">
          <div className="space-y-2">
            <Button variant="default" className="w-full justify-start">
              <Home className="h-4 w-4 mr-3" />
              Query Builder
            </Button>
            <Button 
              variant="ghost" 
              className="w-full justify-start"
              onClick={() => router.push('/er-diagram')}
            >
              <GitBranch className="h-4 w-4 mr-3" />
              ER Diagram
            </Button>
            <Button variant="ghost" className="w-full justify-start">
              <History className="h-4 w-4 mr-3" />
              History
            </Button>
            <Button variant="ghost" className="w-full justify-start">
              <Database className="h-4 w-4 mr-3" />
              Schema
            </Button>
            <Button variant="ghost" className="w-full justify-start">
              <Settings className="h-4 w-4 mr-3" />
              Settings
            </Button>
          </div>
        </nav>

        {/* Status Footer */}
        <div className="p-4 border-t border-border">
          <div className="flex items-center space-x-2">
            <div className="w-2 h-2 bg-green-500 rounded-full"></div>
            <span className="text-sm text-muted-foreground">Connected</span>
          </div>
        </div>
      </div>

      {/* Main Area - 75% width */}
      <div className="flex-1 flex flex-col">
        <AnimatePresence mode="wait">
          {!hasQuery ? (
            // Initial State: Full-width input
            <motion.div
              key="initial"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex-1 flex items-center justify-center p-8"
            >
              <div className="w-full max-w-4xl">
                <div className="text-center mb-8">
                  <h2 className="text-3xl font-bold text-foreground mb-4">
                    What would you like to query?
                  </h2>
                  <p className="text-lg text-muted-foreground">
                    Describe your data needs in natural language, and I'll generate the SQL for you.
                  </p>
                </div>
                
                <Card className="bg-card/60 backdrop-blur-sm border-border shadow-lg">
                  <CardContent className="p-8">
                    <AiPromptInterface 
                      onQueryGenerated={handleQueryGenerated}
                      onQueryExecuted={handleQueryExecutedFromAI}
                      onNewQuery={handleNewQuery}
                    />
                  </CardContent>
                </Card>
              </div>
            </motion.div>
          ) : (
            // Post-Query State: Split layout (35% chat + 40% tabbed area)
            <motion.div
              key="split"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex-1 flex"
            >
              {/* Chat Area - 45.29% of main*/}
              <div className="w-[45.29%] border-r border-border flex flex-col h-full">
                <div className="p-4 border-b border-border">
                  <h3 className="font-semibold text-foreground flex items-center">
                    <MessageSquare className="h-4 w-4 mr-2" />
                    Conversation
                  </h3>
                </div>
                
                {/* Messages - flexible height */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">
                  {messages.map((message) => (
                    <div key={message.id} className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[80%] rounded-lg p-3 ${
                        message.type === 'user' 
                          ? 'bg-primary text-primary-foreground' 
                          : 'bg-muted text-foreground'
                      }`}>
                        <p className="text-sm">{message.content}</p>
                        <span className="text-xs opacity-70 mt-1 block">
                          {message.timestamp.toLocaleTimeString()}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
                
                {/* Follow-up Query Input - fixed at bottom */}
                <div className="p-2 border-t border-border flex-shrink-0">
                  <AiPromptInterface
                    onNewQuery={async (prompt: string) => {
                      // Add user message to conversation
                      const userMessage: Message = {
                        id: Date.now().toString(),
                        type: 'user',
                        content: prompt,
                        timestamp: new Date()
                      }
                      setMessages(prev => [...prev, userMessage])
                      
                      try {
                        setIsGenerating(true)
                        
                        // Include current SQL context in the prompt
                        const contextualPrompt = generatedQuery 
                          ? `Current SQL context:\n\`\`\`sql\n${generatedQuery}\n\`\`\`\n\nFollow-up request: ${prompt}`
                          : prompt
                        
                        const response = await generateQuery({
                          prompt: contextualPrompt,
                          session_id: sessionId,
                          use_workflow: true,
                          reset_database: true, // Reset database to avoid conflicts
                        })
                        
                        if (response.success && response.sql) {
                          setGeneratedQuery(response.sql)
                          setHasQuery(true)
                          setActiveTab("code")
                          
                          const assistantMessage: Message = {
                            id: Date.now().toString(),
                            type: 'assistant',
                            content: response.explanation || 'I\'ve updated the SQL query based on your request. You can review it in the SQL Query Editor.',
                            timestamp: new Date()
                          }
                          setMessages(prev => [...prev, assistantMessage])
                        } else {
                          throw new Error(response.error || 'Failed to generate query')
                        }
                      } catch (error) {
                        const errorMessage: Message = {
                          id: Date.now().toString(),
                          type: 'assistant',
                          content: `Sorry, I couldn't process your request: ${error instanceof Error ? error.message : 'Unknown error'}`,
                          timestamp: new Date()
                        }
                        setMessages(prev => [...prev, errorMessage])
                      } finally {
                        setIsGenerating(false)
                      }
                    }}
                    isLoading={isGenerating}
                    placeholder={generatedQuery ? "Ask a follow-up question about your current SQL..." : "Describe what you want to query..."}
                  />
                </div>
              </div>

              {/* Tabbed Output Area - 40% of main (30% of total) */}
              <div className="w-[65%] flex flex-col h-full">
                <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col min-h-0">
                  <div className="border-b border-border">
                    <TabsList className="h-12 w-full justify-start rounded-none bg-transparent">
                      <TabsTrigger value="code" className="flex items-center space-x-2">
                        <Code2 className="h-4 w-4" />
                        <span>SQL Code</span>
                      </TabsTrigger>
                      <TabsTrigger value="table" className="flex items-center space-x-2">
                        <Table className="h-4 w-4" />
                        <span>Results</span>
                      </TabsTrigger>
                      {tableTabs.map((tab) => (
                        <TabsTrigger 
                          key={tab.id} 
                          value={tab.id} 
                          className="flex items-center space-x-2 group"
                        >
                          <Table className="h-4 w-4" />
                          <span>{tab.title}</span>
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              handleCloseTableTab(tab.id)
                            }}
                            className="ml-1 hover:bg-destructive/20 rounded p-1 opacity-0 group-hover:opacity-100 transition-opacity"
                          >
                            ×
                          </button>
                        </TabsTrigger>
                      ))}
                    </TabsList>
                  </div>
                  
                  <TabsContent value="code" className="flex-1 m-0 p-6 overflow-hidden">
                    <SqlCodeEditor 
                      value={generatedQuery}
                      onChange={setGeneratedQuery}
                      onExecute={() => handleDirectExecution(generatedQuery)}
                      isExecuting={isExecuting}
                    />
                  </TabsContent>
                  
                  <TabsContent value="table" className="flex-1 m-0 p-6 overflow-hidden">
                    {queryResults ? (
                      <QueryExecutionResults 
                        query={generatedQuery} 
                        results={{
                          success: queryResults.success,
                          prompt: generatedQuery, // Use query as prompt for display
                          sql: queryResults.query,
                          columns: queryResults.columns,
                          rows: queryResults.rows,
                          row_count: queryResults.row_count,
                          affected_rows: queryResults.affected_rows,
                          execution_time_ms: queryResults.execution_time_ms,
                          error: queryResults.error_message,
                          metadata: queryResults.metadata,
                          timestamp: queryResults.timestamp,
                          table_results: queryResults.metadata?.table_results || []
                        }}
                        onExecute={() => {}}
                        onOpenTableInNewTab={handleOpenTableInNewTab}
                      />
                    ) : (
                      <div className="flex items-center justify-center h-full text-muted-foreground overflow-auto">
                        <div className="text-center">
                          <Table className="h-12 w-12 mx-auto mb-4 opacity-50" />
                          <p>Execute a query to see results here</p>
                          {isExecuting && (
                            <motion.div 
                              className="mt-4"
                              initial={{ opacity: 0 }}
                              animate={{ opacity: 1 }}
                            >
                              <div className="flex items-center justify-center space-x-2">
                                <motion.div
                                  animate={{ rotate: 360 }}
                                  transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                                  className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full"
                                />
                                <span className="text-sm">Executing query...</span>
                              </div>
                            </motion.div>
                          )}
                        </div>
                      </div>
                    )}
                  </TabsContent>
                  
                  {/* Table Tabs Content */}
                  {tableTabs.map((tab) => (
                    <TabsContent key={tab.id} value={tab.id} className="flex-1 m-0 p-6 overflow-hidden">
                      <div className="h-full">
                        <div className="flex items-center justify-between mb-4">
                          <h3 className="text-lg font-semibold">{tab.title}</h3>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleCloseTableTab(tab.id)}
                            className="text-destructive hover:bg-destructive/20"
                          >
                            Close Tab
                          </Button>
                        </div>
                        <div className="border rounded-lg h-full overflow-hidden">
                          <QueryExecutionResults 
                            query={tab.tableResult.query}
                            results={{
                              success: true,
                              prompt: tab.tableResult.query,
                              sql: tab.tableResult.query,
                              columns: tab.tableResult.columns,
                              rows: tab.tableResult.rows,
                              row_count: tab.tableResult.row_count,
                              affected_rows: tab.tableResult.affected_rows,
                              execution_time_ms: tab.tableResult.execution_time_ms,
                              metadata: {},
                              timestamp: new Date().toISOString(),
                              table_results: [tab.tableResult]
                            }}
                            onExecute={() => {}}
                            onOpenTableInNewTab={handleOpenTableInNewTab}
                          />
                        </div>
                      </div>
                    </TabsContent>
                  ))}
                </Tabs>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}