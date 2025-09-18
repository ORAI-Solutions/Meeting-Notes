import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import axios from 'axios';

type Status = 'idle' | 'running' | 'done' | 'error';

interface ChannelState {
  status: Status;
  progress: number;
  message: string;
  path?: string | null;
}

interface DownloadContextValue {
  llm: ChannelState;
  asr: ChannelState;
  startLlmDownload: (presetId?: string, url?: string, filename?: string) => Promise<void>;
  startAsrDownload: (presetId?: string) => Promise<void>;
  refresh: () => Promise<void>;
}

const DownloadContext = createContext<DownloadContextValue | undefined>(undefined);

export const DownloadProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [llm, setLlm] = useState<ChannelState>({ status: 'idle', progress: 0, message: '' });
  const [asr, setAsr] = useState<ChannelState>({ status: 'idle', progress: 0, message: '' });

  const llmPollRef = useRef<number | null>(null);
  const asrPollRef = useRef<number | null>(null);

  const clearLlmPoll = () => {
    if (llmPollRef.current) {
      clearTimeout(llmPollRef.current);
      llmPollRef.current = null;
    }
  };

  const clearAsrPoll = () => {
    if (asrPollRef.current) {
      clearTimeout(asrPollRef.current);
      asrPollRef.current = null;
    }
  };

  const pollLlm = useCallback(async () => {
    try {
      const r = await axios.get('/settings/llm/download/status');
      setLlm({
        status: (r.data.status || 'idle') as Status,
        progress: r.data.progress || 0,
        message: r.data.message || '',
        path: r.data.path || null,
      });
      if (r.data.status === 'running') {
        llmPollRef.current = window.setTimeout(pollLlm, 1000);
      } else {
        clearLlmPoll();
      }
    } catch {
      // Back off on error but keep polling while running
      llmPollRef.current = window.setTimeout(pollLlm, 2000);
    }
  }, []);

  const pollAsr = useCallback(async () => {
    try {
      const r = await axios.get('/settings/asr/download/status');
      setAsr({
        status: (r.data.status || 'idle') as Status,
        progress: r.data.progress || 0,
        message: r.data.message || '',
        path: r.data.path || null,
      });
      if (r.data.status === 'running') {
        asrPollRef.current = window.setTimeout(pollAsr, 1000);
      } else {
        clearAsrPoll();
      }
    } catch {
      asrPollRef.current = window.setTimeout(pollAsr, 2000);
    }
  }, []);

  const startLlmDownload = useCallback(async (presetId?: string, url?: string, filename?: string) => {
    try {
      setLlm({ status: 'running', progress: 0, message: '' });
      const body: Record<string, any> = {};
      if (url) body.url = url;
      if (filename) body.filename = filename;
      if (presetId && !url) body.preset_id = presetId;
      axios.post('/settings/llm/download', body).catch(() => {});
      if (!llmPollRef.current) {
        llmPollRef.current = window.setTimeout(pollLlm, 500);
      }
    } catch {
      setLlm((prev) => ({ ...prev, status: 'error' }));
    }
  }, [pollLlm]);

  const startAsrDownload = useCallback(async (presetId?: string) => {
    try {
      setAsr({ status: 'running', progress: 0, message: '' });
      const body: Record<string, any> = {};
      if (presetId) body.preset_id = presetId;
      axios.post('/settings/asr/download', body).catch(() => {});
      if (!asrPollRef.current) {
        asrPollRef.current = window.setTimeout(pollAsr, 500);
      }
    } catch {
      setAsr((prev) => ({ ...prev, status: 'error' }));
    }
  }, [pollAsr]);

  const refresh = useCallback(async () => {
    try {
      const l = await axios.get('/settings/llm/download/status');
      setLlm({
        status: (l.data.status || 'idle') as Status,
        progress: l.data.progress || 0,
        message: l.data.message || '',
        path: l.data.path || null,
      });
      if (l.data.status === 'running' && !llmPollRef.current) {
        llmPollRef.current = window.setTimeout(pollLlm, 1000);
      }
    } catch {}
    try {
      const a = await axios.get('/settings/asr/download/status');
      setAsr({
        status: (a.data.status || 'idle') as Status,
        progress: a.data.progress || 0,
        message: a.data.message || '',
        path: a.data.path || null,
      });
      if (a.data.status === 'running' && !asrPollRef.current) {
        asrPollRef.current = window.setTimeout(pollAsr, 1000);
      }
    } catch {}
  }, [pollLlm, pollAsr]);

  useEffect(() => {
    refresh();
    return () => {
      clearLlmPoll();
      clearAsrPoll();
    };
  }, [refresh]);

  return (
    <DownloadContext.Provider value={{ llm, asr, startLlmDownload, startAsrDownload, refresh }}>
      {children}
    </DownloadContext.Provider>
  );
};

export const useDownload = (): DownloadContextValue => {
  const ctx = useContext(DownloadContext);
  if (!ctx) throw new Error('useDownload must be used within DownloadProvider');
  return ctx;
};



