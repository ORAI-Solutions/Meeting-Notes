import React from 'react';
import ReactDOM from 'react-dom/client';
import { ChakraProvider, ColorModeScript, extendTheme } from '@chakra-ui/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import { DownloadProvider } from './context/DownloadContext';

const theme = extendTheme({
  initialColorMode: 'system',
  useSystemColorMode: true,
});

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ChakraProvider theme={theme}>
        <ColorModeScript initialColorMode={theme.config?.initialColorMode} />
        <DownloadProvider>
          <App />
        </DownloadProvider>
      </ChakraProvider>
    </QueryClientProvider>
  </React.StrictMode>
);


