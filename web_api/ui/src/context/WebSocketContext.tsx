/**
 * WebSocket Context for sharing real-time connection across components.
 */

import React, { createContext, useContext, useCallback, useMemo } from 'react';
import { useWebSocket, WebSocketEvent, ConnectionStatus, UseWebSocketReturn } from '@/hooks/useWebSocket';

interface WebSocketContextValue extends UseWebSocketReturn {
  /** Filter events by type */
  getEventsByType: (type: string) => WebSocketEvent[];
  /** Filter events by guild (uses string ID for JavaScript BigInt safety) */
  getEventsByGuild: (guildId: string) => WebSocketEvent[];
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

interface WebSocketProviderProps {
  children: React.ReactNode;
  onEvent?: (event: WebSocketEvent) => void;
}

export const WebSocketProvider: React.FC<WebSocketProviderProps> = ({ children, onEvent }) => {
  const ws = useWebSocket({
    autoReconnect: true,
    reconnectDelay: 3000,
    maxReconnectAttempts: 10,
    pingInterval: 30000,
    onEvent,
  });

  const getEventsByType = useCallback((type: string) => {
    return ws.events.filter(e => e.type === type);
  }, [ws.events]);

  const getEventsByGuild = useCallback((guildId: string) => {
    return ws.events.filter(e => e.guild_id === guildId);
  }, [ws.events]);

  const value = useMemo(() => ({
    ...ws,
    getEventsByType,
    getEventsByGuild,
  }), [ws, getEventsByType, getEventsByGuild]);

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};

export function useWebSocketContext(): WebSocketContextValue {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocketContext must be used within a WebSocketProvider');
  }
  return context;
}

/**
 * Hook to listen for specific event types.
 */
export function useWebSocketEvent(
  eventType: string,
  callback: (event: WebSocketEvent) => void
) {
  const { lastEvent } = useWebSocketContext();

  React.useEffect(() => {
    if (lastEvent && lastEvent.type === eventType) {
      callback(lastEvent);
    }
  }, [lastEvent, eventType, callback]);
}

/**
 * Connection status indicator component.
 */
export const ConnectionStatusIndicator: React.FC<{ className?: string }> = ({ className }) => {
  const { status } = useWebSocketContext();

  const statusConfig: Record<ConnectionStatus, { color: string; label: string }> = {
    connected: { color: 'bg-green-500', label: 'Connected' },
    connecting: { color: 'bg-yellow-500 animate-pulse', label: 'Connecting' },
    disconnected: { color: 'bg-gray-500', label: 'Disconnected' },
    error: { color: 'bg-red-500', label: 'Error' },
  };

  const config = statusConfig[status];

  return (
    <div className={`flex items-center gap-2 ${className || ''}`}>
      <span className={`w-2 h-2 rounded-full ${config.color}`} />
      <span className="text-xs text-[var(--muted)]">{config.label}</span>
    </div>
  );
};

export default WebSocketProvider;
