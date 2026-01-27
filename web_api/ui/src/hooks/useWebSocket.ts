/**
 * WebSocket hook for real-time updates in GuildScout Dashboard.
 */

import { useEffect, useRef, useState, useCallback } from 'react';

export type EventType =
  | 'raid:created'
  | 'raid:updated'
  | 'raid:signup'
  | 'raid:closed'
  | 'raid:locked'
  | 'raid:unlocked'
  | 'activity:new'
  | 'system:status'
  | 'system:health'
  | 'connection:established'
  | 'ping'
  | 'pong';

export interface WebSocketEvent {
  type: EventType;
  guild_id: string;  // String for JavaScript BigInt safety
  data: Record<string, any>;
  timestamp: string;
}

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

export interface UseWebSocketOptions {
  /** Auto-reconnect on disconnect (default: true) */
  autoReconnect?: boolean;
  /** Reconnect delay in ms (default: 3000) */
  reconnectDelay?: number;
  /** Max reconnect attempts (default: 5) */
  maxReconnectAttempts?: number;
  /** Ping interval in ms (default: 30000) */
  pingInterval?: number;
  /** Event handler callback */
  onEvent?: (event: WebSocketEvent) => void;
  /** Connection status change callback */
  onStatusChange?: (status: ConnectionStatus) => void;
}

export interface UseWebSocketReturn {
  /** Current connection status */
  status: ConnectionStatus;
  /** Last received event */
  lastEvent: WebSocketEvent | null;
  /** All events received (limited to last 100) */
  events: WebSocketEvent[];
  /** Send a message to the server */
  send: (data: Record<string, any>) => void;
  /** Manually connect */
  connect: () => void;
  /** Manually disconnect */
  disconnect: () => void;
  /** Subscribe to a guild */
  subscribe: (guildId: string) => void;
  /** Unsubscribe from a guild */
  unsubscribe: (guildId: string) => void;
}

const MAX_EVENTS = 100;

export function useWebSocket(options: UseWebSocketOptions = {}): UseWebSocketReturn {
  const {
    autoReconnect = true,
    reconnectDelay = 3000,
    maxReconnectAttempts = 5,
    pingInterval = 30000,
    onEvent,
    onStatusChange,
  } = options;

  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [lastEvent, setLastEvent] = useState<WebSocketEvent | null>(null);
  const [events, setEvents] = useState<WebSocketEvent[]>([]);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const mountedRef = useRef(true);

  // Update status and notify
  const updateStatus = useCallback((newStatus: ConnectionStatus) => {
    if (!mountedRef.current) return;
    setStatus(newStatus);
    onStatusChange?.(newStatus);
  }, [onStatusChange]);

  // Handle incoming messages
  const handleMessage = useCallback((event: MessageEvent) => {
    if (!mountedRef.current) return;

    try {
      const data = JSON.parse(event.data) as WebSocketEvent;

      // Ignore pong messages
      if (data.type === 'pong') return;

      setLastEvent(data);
      setEvents(prev => {
        const newEvents = [data, ...prev];
        return newEvents.slice(0, MAX_EVENTS);
      });

      onEvent?.(data);
    } catch (e) {
      console.error('Failed to parse WebSocket message:', e);
    }
  }, [onEvent]);

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    // Clean up existing connection
    if (wsRef.current) {
      wsRef.current.close();
    }

    updateStatus('connecting');

    // Build WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    try {
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        if (!mountedRef.current) return;
        updateStatus('connected');
        reconnectAttemptsRef.current = 0;

        // Start ping interval
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
        }
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, pingInterval);
      };

      ws.onmessage = handleMessage;

      ws.onclose = (event) => {
        if (!mountedRef.current) return;

        // Clear ping interval
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }

        // Don't reconnect on normal close or auth errors
        if (event.code === 1000 || event.code === 4001) {
          updateStatus('disconnected');
          return;
        }

        updateStatus('disconnected');

        // Auto-reconnect
        if (autoReconnect && reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current++;
          reconnectTimeoutRef.current = setTimeout(() => {
            if (mountedRef.current) {
              connect();
            }
          }, reconnectDelay * reconnectAttemptsRef.current);
        }
      };

      ws.onerror = () => {
        if (!mountedRef.current) return;
        updateStatus('error');
      };

      wsRef.current = ws;
    } catch (e) {
      console.error('Failed to create WebSocket:', e);
      updateStatus('error');
    }
  }, [autoReconnect, reconnectDelay, maxReconnectAttempts, pingInterval, handleMessage, updateStatus]);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    // Clear reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // Clear ping interval
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }

    // Close WebSocket
    if (wsRef.current) {
      wsRef.current.close(1000, 'Manual disconnect');
      wsRef.current = null;
    }

    updateStatus('disconnected');
    reconnectAttemptsRef.current = maxReconnectAttempts; // Prevent auto-reconnect
  }, [maxReconnectAttempts, updateStatus]);

  // Send message
  const send = useCallback((data: Record<string, any>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  // Subscribe to guild
  const subscribe = useCallback((guildId: string) => {
    send({ type: 'subscribe', guild_id: guildId });
  }, [send]);

  // Unsubscribe from guild
  const unsubscribe = useCallback((guildId: string) => {
    send({ type: 'unsubscribe', guild_id: guildId });
  }, [send]);

  // Connect on mount
  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      disconnect();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    status,
    lastEvent,
    events,
    send,
    connect,
    disconnect,
    subscribe,
    unsubscribe,
  };
}

export default useWebSocket;
