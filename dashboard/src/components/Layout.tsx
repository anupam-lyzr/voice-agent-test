import { useState } from 'react'
import type { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Button } from './ui/button'
import { Badge } from './ui/badge'
import { 
  Phone, 
  BarChart3, 
  TestTube, 
  Menu,
  X
} from 'lucide-react'

import  type { LucideIcon } from 'lucide-react'
interface LayoutProps {
  children: ReactNode
}

interface NavigationItem {
  name: string
  href: string
  icon: LucideIcon
}

export default function Layout({ children }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [productionMode, setProductionMode] = useState(false)
  const location = useLocation()

  const navigation: NavigationItem[] = [
    { name: 'Dashboard', href: '/', icon: BarChart3 },
    { name: 'Testing', href: '/testing', icon: TestTube },
  ]

  const isActive = (href: string): boolean => location.pathname === href

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div className={`
        fixed inset-y-0 left-0 z-50 w-64 bg-white shadow-lg transform transition-transform duration-300 ease-in-out
        lg:translate-x-0 lg:static lg:inset-0
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        <div className="flex items-center justify-between h-16 px-6 border-b">
          <div className="flex items-center space-x-2">
            <Phone className="h-8 w-8 text-blue-600" />
            <span className="text-xl font-bold">Voice Agent</span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden"
          >
            <X className="h-6 w-6" />
          </Button>
        </div>

        {/* Production Mode Toggle */}
        <div className="p-4 border-b">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Mode</span>
            <Button
              variant={productionMode ? "destructive" : "outline"}
              size="sm"
              onClick={() => setProductionMode(!productionMode)}
            >
              {productionMode ? 'PRODUCTION' : 'TESTING'}
            </Button>
          </div>
          <div className="mt-2">
            <Badge variant={productionMode ? "destructive" : "secondary"}>
              {productionMode ? '🔴 LIVE CALLS' : '🧪 TEST MODE'}
            </Badge>
          </div>
        </div>

        {/* Navigation */}
        <nav className="mt-6 px-4">
          <ul className="space-y-2">
            {navigation.map((item) => {
              const Icon = item.icon
              return (
                <li key={item.name}>
                  <Link
                    to={item.href}
                    className={`
                      flex items-center space-x-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors
                      ${isActive(item.href) 
                        ? 'bg-blue-100 text-blue-700' 
                        : 'text-gray-700 hover:bg-gray-100'
                      }
                    `}
                    onClick={() => setSidebarOpen(false)}
                  >
                    <Icon className="h-5 w-5" />
                    <span>{item.name}</span>
                  </Link>
                </li>
              )
            })}
          </ul>
        </nav>

        {/* System Status */}
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-600">System Status</span>
            <Badge variant="outline" className="text-green-600">
              ● Online
            </Badge>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="lg:pl-64">
        {/* Top bar */}
        <div className="sticky top-0 z-30 bg-white border-b px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setSidebarOpen(true)}
                className="lg:hidden"
              >
                <Menu className="h-6 w-6" />
              </Button>
              <h1 className="text-2xl font-bold text-gray-900">
                Voice Agent Dashboard
              </h1>
            </div>
            <div className="flex items-center space-x-4">
              <Badge variant={productionMode ? "destructive" : "secondary"}>
                {productionMode ? 'PRODUCTION MODE' : 'TEST MODE'}
              </Badge>
            </div>
          </div>
        </div>

        {/* Page content */}
        <main className="p-6">
          {children}
        </main>
      </div>
    </div>
  )
}