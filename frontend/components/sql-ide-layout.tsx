"use client"

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useRouter } from "next/navigation"
import { 
  Sparkles, 
  Code2, 
  MessageSquare, 
  Table,
  Play,
  Home,
  GitBranch,
  ChevronDown,
  ChevronUp,
  Eye,
  FileText,
  Download,
  Menu,
  X
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { AiPromptInterface } from "@/components/ai-prompt-interface"
import { SqlCodeEditor } from "./sql-code-editor"
import { QueryExecutionResults } from "@/components/query-execution-results"
import { executeQuery, generateQuery, clearConversation, getSchemaAsMermaid } from "@/lib/api"
import type { AIQueryResponse, ExecuteQueryResponse, EnhanceSQLRequest, TableResult, MermaidSchemaResponse } from "@/lib/api"

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
  const [erDiagramData, setErDiagramData] = useState<MermaidSchemaResponse | null>(null)
  const [isLoadingErDiagram, setIsLoadingErDiagram] = useState(false)
  const [showErDiagram, setShowErDiagram] = useState(false)
  const [erDiagramView, setErDiagramView] = useState<'diagram' | 'code'>('diagram')
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Mermaid renderer function
  const renderMermaidDiagram = async (mermaidCode: string, elementId: string) => {
    try {
      // Dynamically import mermaid to avoid SSR issues
      const mermaid = (await import('mermaid')).default
      
      mermaid.initialize({
        startOnLoad: false,
        theme: 'default',
        themeVariables: {
          fontFamily: 'system-ui, -apple-system, sans-serif',
          fontSize: '14px'
        }
      })

      const element = document.getElementById(elementId)
      if (element) {
        element.innerHTML = '' // Clear previous content
        const { svg } = await mermaid.render(`mermaid-${Date.now()}`, mermaidCode)
        element.innerHTML = svg
      }
    } catch (error) {
      console.error('Mermaid rendering error:', error)
      const element = document.getElementById(elementId)
      if (element) {
        element.innerHTML = `
          <div class="text-red-500 p-4 border border-red-200 rounded">
            <p class="font-semibold">Diagram Rendering Error</p>
            <p class="text-sm mt-1">Could not render the diagram. Please check the Mermaid code syntax.</p>
          </div>
        `
      }
    }
  }

  // Effect to render diagram when ER data changes and diagram view is active
  useEffect(() => {
    if (erDiagramData?.has_tables && erDiagramData.mermaid && showErDiagram && erDiagramView === 'diagram') {
      setTimeout(() => {
        renderMermaidDiagram(erDiagramData.mermaid, 'mermaid-diagram-container')
      }, 100) // Small delay to ensure DOM is ready
    }
  }, [erDiagramData, showErDiagram, erDiagramView])

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
    setActiveTab("code") // Focus on the code editor to review the generated SQL
    
    // Add to conversation - simpler message without showing SQL
    const newMessage: Message = {
      id: Date.now().toString(),
      type: 'assistant',
      content: 'I\'ve generated the SQL query for you. You can review and edit it in the code editor, then execute it.',
      timestamp: new Date()
    }
    setMessages(prev => [...prev, newMessage])
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

  const handleGenerateErDiagram = async () => {
    setIsLoadingErDiagram(true)
    try {
      const erData = await getSchemaAsMermaid()
      setErDiagramData(erData)
      setShowErDiagram(true)
      setActiveTab("er-diagram")
    } catch (error) {
      console.error('Failed to generate ER diagram:', error)
      // You might want to show an error message to the user here
    } finally {
      setIsLoadingErDiagram(false)
    }
  }

  return (
    <div className="h-screen flex bg-background overflow-hidden">
      {/* Mobile Menu Button */}
      <div className="lg:hidden fixed top-4 left-4 z-50">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="bg-background/80 backdrop-blur-sm"
        >
          {sidebarOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
        </Button>
      </div>

      {/* Mobile Sidebar Overlay */}
      {sidebarOpen && (
        <div 
          className="lg:hidden fixed inset-0 bg-black/50 z-40"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar - responsive width */}
      <div className={`
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        fixed lg:relative inset-y-0 left-0 z-40 lg:z-auto
        w-64 lg:w-1/6 xl:w-1/7 bg-card border-r border-border flex flex-col 
        min-w-[200px] max-w-[300px] transition-transform duration-200 ease-in-out
      `}>
        {/* Brand Header */}
        <div className="p-4 lg:p-6 border-b border-border">
          <div className="flex items-center space-x-3">
            <div className="flex items-center justify-center w-8 h-8 lg:w-10 lg:h-10 bg-primary/10 rounded-lg">
              <Sparkles className="h-5 w-5 lg:h-6 lg:w-6 text-primary" />
            </div>
            <div>
              <h1 className="text-lg lg:text-xl font-bold text-foreground">AutoSQL</h1>
              <p className="text-xs lg:text-sm text-muted-foreground">AI SQL Assistant</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-2 lg:p-4">
          <div className="space-y-4">
            <Button variant="default" className="w-full justify-start text-sm lg:text-base">
              <Home className="h-4 w-4 mr-2 lg:mr-3" />
              <span>Query Builder</span>
            </Button>
            
            {/* Features List */}
            <div className="mt-6">
              <h3 className="text-sm font-semibold text-muted-foreground mb-3 px-2">Features</h3>
              <div className="space-y-2">
                <div className="flex items-center px-2 py-2 text-sm text-muted-foreground">
                  <Code2 className="h-4 w-4 mr-3" />
                  Get SQL code
                </div>
                <div className="flex items-center px-2 py-2 text-sm text-muted-foreground">
                  <Table className="h-4 w-4 mr-3" />
                  Visualize data
                </div>
              </div>
            </div>
          </div>
        </nav>

        {/* Status Footer */}
        <div className="p-2 lg:p-4 border-t border-border">
          {/* GitHub Credit */}
          <div className="mb-3">
            <a 
              href="https://github.com/Ayush-D2004/AutoSQL" 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-xs text-muted-foreground hover:text-primary transition-colors underline"
            >
              Made by Ayush Dhoble
            </a>
          </div>
          
          <div className="flex items-center space-x-2">
            <div className="w-2 h-2 bg-green-500 rounded-full"></div>
            <span className="text-xs lg:text-sm text-muted-foreground">Connected</span>
          </div>
        </div>
      </div>

      {/* Main Area - responsive */}
      <div className="flex-1 flex flex-col min-w-0 lg:ml-0">
        <AnimatePresence mode="wait">
          {!hasQuery ? (
            // Initial State: Full-width input
            <motion.div
              key="initial"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex-1 flex items-center justify-center p-4 lg:p-8"
            >
              <div className="w-full max-w-4xl">
                <div className="text-center mb-6 lg:mb-8">
                  <h2 className="text-2xl lg:text-3xl font-bold text-foreground mb-3 lg:mb-4">
                    What would you like to query?
                  </h2>
                  <p className="text-base lg:text-lg text-muted-foreground">
                    Describe your data needs in natural language, and I'll generate the SQL for you.
                  </p>
                </div>
                
                <Card className="bg-card/60 backdrop-blur-sm border-border shadow-lg">
                  <CardContent className="p-4 lg:p-8">
                    <AiPromptInterface 
                      onQueryGenerated={handleQueryGenerated}
                      onNewQuery={handleNewQuery}
                    />
                  </CardContent>
                </Card>
              </div>
            </motion.div>
          ) : (
            // Post-Query State: Responsive split layout
            <motion.div
              key="split"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex-1 flex flex-col lg:flex-row"
            >
              {/* Chat Area - responsive */}
              <div className="w-full lg:w-[45.29%] border-b lg:border-b-0 lg:border-r border-border flex flex-col h-full max-h-screen order-2 lg:order-1">
                <div className="p-3 lg:p-4 border-b border-border flex-shrink-0">
                  <h3 className="font-semibold text-foreground flex items-center text-sm lg:text-base">
                    <MessageSquare className="h-4 w-4 mr-2" />
                    Conversation
                  </h3>
                </div>
                
                {/* Messages - flexible height with proper scrolling */}
                <div className="flex-1 overflow-y-auto p-3 lg:p-4 space-y-3 lg:space-y-4 min-h-0 scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100">
                  {messages.map((message) => (
                    <div key={message.id} className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[85%] lg:max-w-[80%] rounded-lg p-2 lg:p-3 ${
                        message.type === 'user' 
                          ? 'bg-primary text-primary-foreground' 
                          : 'bg-muted text-foreground'
                      }`}>
                        <p className="text-xs lg:text-sm">{message.content}</p>
                        <span className="text-xs opacity-70 mt-1 block">
                          {message.timestamp.toLocaleTimeString()}
                        </span>
                      </div>
                    </div>
                  ))}
                  {/* Show AI thinking indicator */}
                  {isGenerating && (
                    <div className="flex justify-start">
                      <div className="bg-muted text-foreground rounded-lg p-2 lg:p-3 max-w-[85%] lg:max-w-[80%]">
                        <div className="flex items-center space-x-2">
                          <div className="flex space-x-1">
                            {[0, 1, 2].map((i) => (
                              <motion.div
                                key={i}
                                animate={{
                                  scale: [1, 1.2, 1],
                                  opacity: [0.5, 1, 0.5],
                                }}
                                transition={{
                                  duration: 1,
                                  repeat: Number.POSITIVE_INFINITY,
                                  delay: i * 0.2,
                                }}
                                className="w-2 h-2 bg-primary rounded-full"
                              />
                            ))}
                          </div>
                          <span className="text-xs lg:text-sm text-muted-foreground">AI is thinking...</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
                
                {/* Follow-up Query Input - fixed at bottom */}
                <div className="p-3 lg:p-4 border-t border-border flex-shrink-0 bg-background">
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

              {/* Tabbed Output Area - responsive */}
              <div className="w-full lg:w-[54.71%] flex flex-col h-full max-h-screen order-1 lg:order-2">
                <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col min-h-0">
                  <div className="border-b border-border flex-shrink-0">
                    <TabsList className="h-10 lg:h-12 w-full justify-start rounded-none bg-transparent overflow-x-auto">
                      <TabsTrigger value="code" className="flex items-center space-x-1 lg:space-x-2 text-xs lg:text-sm whitespace-nowrap">
                        <Code2 className="h-3 w-3 lg:h-4 lg:w-4" />
                        <span>SQL Code</span>
                      </TabsTrigger>
                      <TabsTrigger value="table" className="flex items-center space-x-1 lg:space-x-2 text-xs lg:text-sm whitespace-nowrap">
                        <Table className="h-3 w-3 lg:h-4 lg:w-4" />
                        <span>Results</span>
                      </TabsTrigger>
                      {showErDiagram && (
                        <TabsTrigger value="er-diagram" className="flex items-center space-x-1 lg:space-x-2 text-xs lg:text-sm whitespace-nowrap">
                          <GitBranch className="h-3 w-3 lg:h-4 lg:w-4" />
                          <span className="hidden sm:inline">ER Diagram</span>
                          <span className="sm:hidden">ER</span>
                        </TabsTrigger>
                      )}
                      {tableTabs.map((tab) => (
                        <TabsTrigger 
                          key={tab.id} 
                          value={tab.id} 
                          className="flex items-center space-x-1 lg:space-x-2 group text-xs lg:text-sm whitespace-nowrap"
                        >
                          <Table className="h-3 w-3 lg:h-4 lg:w-4" />
                          <span className="max-w-[100px] truncate">{tab.title}</span>
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
                  
                  <TabsContent value="code" className="flex-1 m-0 p-3 lg:p-6 overflow-y-auto">
                    <div className="h-full pb-4 lg:pb-8">
                      <SqlCodeEditor 
                        value={generatedQuery}
                        onChange={setGeneratedQuery}
                        onExecute={() => handleDirectExecution(generatedQuery)}
                        isExecuting={isExecuting}
                      />
                    </div>
                  </TabsContent>
                  
                  <TabsContent value="table" className="flex-1 m-0 p-3 lg:p-6 overflow-hidden">
                    {queryResults ? (
                      <div className="h-full flex flex-col">
                        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-2 lg:gap-0 mb-4 flex-shrink-0">
                          <h3 className="text-base lg:text-lg font-semibold">Query Results</h3>
                          <Button
                            onClick={handleGenerateErDiagram}
                            disabled={isLoadingErDiagram}
                            variant="outline"
                            size="sm"
                            className="self-start sm:self-auto"
                          >
                            <GitBranch className="h-3 w-3 lg:h-4 lg:w-4 mr-1 lg:mr-2" />
                            <span className="text-xs lg:text-sm">{isLoadingErDiagram ? "Generating..." : "Generate ER Diagram"}</span>
                          </Button>
                        </div>
                        <div className="flex-1 overflow-hidden">
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
                        </div>
                      </div>
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
                        <div className="flex items-center justify-between mb-4 flex-shrink-0">
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
                  
                  {/* ER Diagram Tab Content */}
                  {showErDiagram && (
                    <TabsContent value="er-diagram" className="flex-1 m-0 p-3 lg:p-6 overflow-hidden">
                      <div className="h-full flex flex-col">
                        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 lg:gap-0 mb-4 flex-shrink-0">
                          <h3 className="text-base lg:text-lg font-semibold">Entity Relationship Diagram</h3>
                          <div className="flex items-center space-x-2">
                            {erDiagramData?.has_tables && erDiagramData.mermaid && (
                              <Button
                                onClick={() => {
                                  // Download ER diagram as SVG
                                  const svgElement = document.querySelector('#mermaid-diagram-container svg');
                                  if (svgElement) {
                                    const svgData = new XMLSerializer().serializeToString(svgElement);
                                    const blob = new Blob([svgData], { type: 'image/svg+xml' });
                                    const url = URL.createObjectURL(blob);
                                    const link = document.createElement('a');
                                    link.href = url;
                                    link.download = 'er-diagram.svg';
                                    document.body.appendChild(link);
                                    link.click();
                                    document.body.removeChild(link);
                                    URL.revokeObjectURL(url);
                                  }
                                }}
                                variant="outline"
                                size="sm"
                              >
                                <Download className="h-3 w-3 lg:h-4 lg:w-4 mr-1 lg:mr-2" />
                                <span className="text-xs lg:text-sm">Download SVG</span>
                              </Button>
                            )}
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                setShowErDiagram(false)
                                setActiveTab("table")
                              }}
                              className="text-destructive hover:bg-destructive/20"
                            >
                              <span className="text-xs lg:text-sm">Close</span>
                            </Button>
                          </div>
                        </div>
                        
                        <div className="border rounded-lg flex-1 overflow-hidden bg-white">
                          {erDiagramData ? (
                            <div className="h-full flex flex-col">
                              {erDiagramData.has_tables ? (
                                <div className="h-full flex flex-col">
                                  {/* Toggle Buttons */}
                                  <div className="flex space-x-2 p-4 border-b flex-shrink-0">
                                    <Button
                                      onClick={() => setErDiagramView('diagram')}
                                      variant={erDiagramView === 'diagram' ? 'default' : 'outline'}
                                      size="sm"
                                      className="flex items-center space-x-2"
                                    >
                                      <Eye className="h-3 w-3 lg:h-4 lg:w-4" />
                                      <span className="text-xs lg:text-sm">Visual Diagram</span>
                                    </Button>
                                    <Button
                                      onClick={() => setErDiagramView('code')}
                                      variant={erDiagramView === 'code' ? 'default' : 'outline'}
                                      size="sm"
                                      className="flex items-center space-x-2"
                                    >
                                      <FileText className="h-3 w-3 lg:h-4 lg:w-4" />
                                      <span className="text-xs lg:text-sm">Mermaid Code</span>
                                    </Button>
                                  </div>

                                  {/* Content Area with proper scrolling */}
                                  <div className="flex-1 overflow-hidden">
                                    {/* Visual Diagram Section */}
                                    {erDiagramView === 'diagram' && (
                                      <motion.div
                                        initial={{ opacity: 0, y: -10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ duration: 0.2 }}
                                        className="h-full flex flex-col"
                                      >
                                        <div className="p-4 pb-2 flex-shrink-0">
                                          <h4 className="font-semibold flex items-center text-sm lg:text-base">
                                            <Eye className="h-3 w-3 lg:h-4 lg:w-4 mr-2" />
                                            Visual ER Diagram
                                          </h4>
                                        </div>
                                        <div className="flex-1 overflow-auto scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100 p-4 pt-0">
                                          <div className="border rounded-lg p-4 bg-gray-50 min-h-full">
                                            <div 
                                              id="mermaid-diagram-container" 
                                              className="w-full h-auto min-h-[400px] flex items-center justify-center"
                                            >
                                              <div className="text-center text-gray-500">
                                                <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full mx-auto mb-2"></div>
                                                <p className="text-xs lg:text-sm">Rendering diagram...</p>
                                              </div>
                                            </div>
                                          </div>
                                        </div>
                                      </motion.div>
                                    )}

                                    {/* Mermaid Code Section */}
                                    {erDiagramView === 'code' && (
                                      <motion.div
                                        initial={{ opacity: 0, y: -10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ duration: 0.2 }}
                                        className="h-full flex flex-col"
                                      >
                                        <div className="p-4 pb-2 flex-shrink-0">
                                          <h4 className="font-semibold flex items-center text-sm lg:text-base">
                                            <FileText className="h-3 w-3 lg:h-4 lg:w-4 mr-2" />
                                            Mermaid ER Diagram Code
                                          </h4>
                                        </div>
                                        <div className="flex-1 overflow-hidden p-4 pt-0">
                                          <div className="border rounded-lg overflow-hidden h-full flex flex-col">
                                            <div className="bg-gray-50 px-3 py-2 border-b flex justify-between items-center flex-shrink-0">
                                              <span className="text-xs lg:text-sm font-medium text-gray-700">mermaid</span>
                                              <Button
                                                onClick={() => {
                                                  navigator.clipboard.writeText(erDiagramData.mermaid)
                                                  // You could add a toast notification here
                                                }}
                                                variant="ghost"
                                                size="sm"
                                                className="text-xs"
                                              >
                                                Copy
                                              </Button>
                                            </div>
                                            <div className="flex-1 overflow-auto scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100">
                                              <pre className="text-xs lg:text-sm p-4 bg-white h-full">
                                                <code>{erDiagramData.mermaid}</code>
                                              </pre>
                                            </div>
                                          </div>
                                        </div>
                                        <div className="p-4 pt-0 flex-shrink-0">
                                          <p className="text-xs lg:text-sm text-gray-600">
                                            You can copy this code to{' '}
                                            <a 
                                              href="https://mermaid.live" 
                                              target="_blank" 
                                              rel="noopener noreferrer"
                                              className="text-blue-500 underline hover:text-blue-700"
                                            >
                                              mermaid.live
                                            </a>{' '}
                                            for external editing or sharing.
                                          </p>
                                        </div>
                                      </motion.div>
                                    )}
                                  </div>

                                  {/* Metadata */}
                                  <div className="text-xs text-gray-500 p-4 border-t flex-shrink-0">
                                    <p>Generated at: {new Date(erDiagramData.generated_at).toLocaleString()}</p>
                                    <p>Status: {erDiagramData.message}</p>
                                  </div>
                                </div>
                              ) : (
                                <div className="flex items-center justify-center h-full">
                                  <div className="text-center">
                                    <GitBranch className="h-12 w-12 lg:h-16 lg:w-16 mx-auto mb-4 text-gray-400" />
                                    <p className="text-sm lg:text-base text-gray-600 mb-2">{erDiagramData.message}</p>
                                    <p className="text-xs lg:text-sm text-gray-500">
                                      Create some tables first to see the ER diagram.
                                    </p>
                                  </div>
                                </div>
                              )}
                            </div>
                          ) : (
                            <div className="flex items-center justify-center h-full">
                              <div className="text-center">
                                <motion.div
                                  animate={{ rotate: 360 }}
                                  transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                                  className="w-6 h-6 lg:w-8 lg:h-8 border-2 border-primary border-t-transparent rounded-full mx-auto mb-4"
                                />
                                <p className="text-sm lg:text-base text-gray-600">Loading ER diagram...</p>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </TabsContent>
                  )}
                </Tabs>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}