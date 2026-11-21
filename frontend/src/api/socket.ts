import { useEffect, useRef, useSyncExternalStore } from 'react';
import { io, type Socket } from 'socket.io-client';
import type { ClientToServerEvents, ServerToClientEvents } from './types';

export type AppSocket = Socket<ServerToClientEvents, ClientToServerEvents>;
export type ConnectionState = 'connected' | 'disconnected' | 'reconnecting';

const WS_URL = import.meta.env.VITE_WS_URL || 'http://localhost:4000';

let socket: AppSocket | null = null;
let state: ConnectionState = 'disconnected';
const listeners = new Set<() => void>();

function setState(next: ConnectionState) {
  if (state === next) return;
  state = next;
  listeners.forEach((l) => l());
}

/** Jedno połączenie na całą aplikację; socket.io sam ponawia połączenie z rosnącym odstępem. */
export function getSocket(): AppSocket {
  if (socket) return socket;
  socket = io(WS_URL, {
    transports: ['websocket'],
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 15000,
    timeout: 8000,
  });
  socket.on('connect', () => setState('connected'));
  socket.on('disconnect', () => setState('disconnected'));
  socket.on('connect_error', () => setState(socket?.active ? 'reconnecting' : 'disconnected'));
  socket.io.on('reconnect_attempt', () => setState('reconnecting'));
  socket.io.on('reconnect_failed', () => setState('disconnected'));
  return socket;
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

export function useConnectionState(): ConnectionState {
  getSocket();
  return useSyncExternalStore(subscribe, () => state);
}

/** Subskrypcja zdarzenia socketu z aktualnym handlerem (bez ponownego podpinania przy każdym renderze). */
export function useSocketEvent<E extends keyof ServerToClientEvents>(event: E, handler: ServerToClientEvents[E]): void {
  const ref = useRef(handler);
  useEffect(() => {
    ref.current = handler;
  });
  useEffect(() => {
    const s = getSocket();
    const fn = ((...args: Parameters<ServerToClientEvents[E]>) =>
      (ref.current as (...a: Parameters<ServerToClientEvents[E]>) => void)(...args)) as ServerToClientEvents[E];
    // typy socket.io dla generycznego zdarzenia wymagają rzutowania
    (s.on as (e: E, f: ServerToClientEvents[E]) => void)(event, fn);
    return () => {
      (s.off as (e: E, f: ServerToClientEvents[E]) => void)(event, fn);
    };
  }, [event]);
}
