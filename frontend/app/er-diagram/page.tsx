"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Loader2, Database, Home, RefreshCw } from "lucide-react"
import { useRouter } from "next/navigation"
import { getSchemaAsMermaid, type MermaidSchemaResponse } from "@/lib/api"

export default function ERDiagramPage() {
  const [schemaData, setSchemaData] = useState<MermaidSchemaResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const router = useRouter()

  const fetchSchema = async () => {
    try {
      setLoading(true)
      setError(null)
      
      const data = await getSchemaAsMermaid()
      setSchemaData(data)
      
      // If we have tables, render the mermaid diagram
      if (data.has_tables && data.mermaid) {
        await renderMermaidDiagram(data.mermaid)
      }
      
    } catch (err) {
      console.error('Schema fetch error:', err)
      setError(err instanceof Error ? err.message : 'Failed to fetch schema')
    } finally {
      setLoading(false)
    }
  }

  const renderMermaidDiagram = async (mermaidCode: string) => {
    try {
      // For now, just display the Mermaid code as text
      // Later we can integrate with a proper Mermaid renderer
      const element = document.getElementById('mermaid-diagram')
      if (element) {
        element.innerHTML = `
          <div class="bg-gray-50 p-4 rounded border">
            <h4 class="font-semibold mb-2">Mermaid ER Diagram Code:</h4>
            <pre class="text-sm bg-white p-3 rounded border overflow-auto"><code>${mermaidCode}</code></pre>
            <p class="text-sm text-gray-600 mt-2">
              Copy this code to <a href="https://mermaid.live" target="_blank" class="text-blue-500 underline">mermaid.live</a> 
              to view the visual diagram.
            </p>
          </div>
        `
      }
      
    } catch (err) {
      console.error('Mermaid rendering error:', err)
      setError('Failed to render diagram')
    }
  }

  useEffect(() => {
    fetchSchema()
  }, [])

  const handleRefresh = () => {
    fetchSchema()
  }

  const handleGoHome = () => {
    router.push('/')
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4" />
          <p className="text-gray-600">Loading database schema...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center justify-between mb-6">
            <h1 className="text-3xl font-bold flex items-center gap-2">
              <Database className="h-8 w-8" />
              ER Diagram
            </h1>
            <div className="flex gap-2">
              <Button onClick={handleRefresh} variant="outline">
                <RefreshCw className="h-4 w-4 mr-2" />
                Retry
              </Button>
              <Button onClick={handleGoHome} variant="outline">
                <Home className="h-4 w-4 mr-2" />
                Home
              </Button>
            </div>
          </div>
          
          <Alert className="mb-6">
            <AlertDescription>
              <strong>Error:</strong> {error}
            </AlertDescription>
          </Alert>
        </div>
      </div>
    )
  }

  if (!schemaData?.has_tables) {
    return (
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center justify-between mb-6">
            <h1 className="text-3xl font-bold flex items-center gap-2">
              <Database className="h-8 w-8" />
              ER Diagram
            </h1>
            <div className="flex gap-2">
              <Button onClick={handleRefresh} variant="outline">
                <RefreshCw className="h-4 w-4 mr-2" />
                Refresh
              </Button>
              <Button onClick={handleGoHome}>
                <Home className="h-4 w-4 mr-2" />
                Go to Home
              </Button>
            </div>
          </div>
          
          <Card>
            <CardHeader>
              <CardTitle>No Database Schema Found</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-center py-8">
                <Database className="h-16 w-16 mx-auto mb-4 text-gray-400" />
                <p className="text-gray-600 mb-4">
                  No tables found in your database. Create some tables first to see the ER diagram.
                </p>
                <p className="text-sm text-gray-500 mb-6">
                  Go to the main page and execute some CREATE TABLE statements, or use AI to generate a schema.
                </p>
                <Button onClick={handleGoHome}>
                  <Home className="h-4 w-4 mr-2" />
                  Go to Main Page
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Database className="h-8 w-8" />
            Database ER Diagram
          </h1>
          <div className="flex gap-2">
            <Button onClick={handleRefresh} variant="outline">
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
            <Button onClick={handleGoHome} variant="outline">
              <Home className="h-4 w-4 mr-2" />
              Home
            </Button>
          </div>
        </div>
        
        <Card>
          <CardHeader>
            <CardTitle>Entity Relationship Diagram</CardTitle>
            <p className="text-sm text-gray-600">
              Visual representation of your database schema and relationships
            </p>
          </CardHeader>
          <CardContent>
            <div className="border rounded-lg p-4 bg-white overflow-auto">
              <div 
                id="mermaid-diagram" 
                className="w-full min-h-[400px] flex items-center justify-center"
              >
                <div className="text-center">
                  <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4" />
                  <p className="text-gray-600">Rendering diagram...</p>
                </div>
              </div>
            </div>
            
            {schemaData && (
              <div className="mt-4 text-xs text-gray-500">
                <p>Generated at: {new Date(schemaData.generated_at).toLocaleString()}</p>
                <p>Status: {schemaData.message}</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}