import { BrowserRouter } from 'react-router-dom';
import { SystemProvider } from './contexts/SystemContext';
import AppRoutes from './routes/AppRoutes';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <SystemProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </SystemProvider>
    </QueryClientProvider>
  );
}

export default App;
