import { MantineProvider } from '@mantine/core';
import { DatesProvider } from '@mantine/dates';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { lazy, Suspense } from 'react';
import { HashRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { Loading } from '../components/PageState';
import { Layout } from './Layout';
import { RealtimeProvider } from './realtime';
import { theme } from './theme';

// ekrany ładowane dopiero przy wejściu (wykresy i graf to osobne, duże paczki)
const Statistics = lazy(() => import('../pages/Statistics').then((m) => ({ default: m.Statistics })));
const Entities = lazy(() => import('../pages/Entities').then((m) => ({ default: m.Entities })));
const EntityDetail = lazy(() => import('../pages/EntityDetail').then((m) => ({ default: m.EntityDetail })));
const Reports = lazy(() => import('../pages/Reports').then((m) => ({ default: m.Reports })));
const ModuleRoute = lazy(() => import('../pages/ModulePage').then((m) => ({ default: m.ModuleRoute })));
const History = lazy(() => import('../pages/History').then((m) => ({ default: m.History })));
const FindingDetail = lazy(() => import('../pages/FindingDetail').then((m) => ({ default: m.FindingDetail })));
const Calibration = lazy(() => import('../pages/Calibration').then((m) => ({ default: m.Calibration })));
const NotFound = lazy(() => import('../pages/NotFound').then((m) => ({ default: m.NotFound })));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000, refetchOnWindowFocus: false },
  },
});

export function App() {
  return (
    <MantineProvider theme={theme} defaultColorScheme="light" forceColorScheme="light">
      <DatesProvider settings={{ locale: 'pl', firstDayOfWeek: 1 }}>
        <QueryClientProvider client={queryClient}>
          <HashRouter>
            <RealtimeProvider>
              <Routes>
                <Route element={<Layout />}>
                  {[
                    { index: true, el: <ToStatistics /> },
                    { path: 'statistics', el: <Statistics /> },
                    { path: 'entities', el: <Entities /> },
                    { path: 'entities/:id', el: <EntityDetail /> },
                    { path: 'reports', el: <Reports /> },
                    { path: 'reports/:id', el: <Reports /> },
                    { path: 'modules/:key', el: <ModuleRoute /> },
                    { path: 'findings/:id', el: <FindingDetail /> },
                    { path: 'history', el: <History /> },
                    { path: 'calibration', el: <Calibration /> },
                    { path: '*', el: <NotFound /> },
                  ].map((r) =>
                    r.index ? (
                      <Route key="index" index element={<Suspense fallback={<Loading />}>{r.el}</Suspense>} />
                    ) : (
                      <Route key={r.path} path={r.path} element={<Suspense fallback={<Loading />}>{r.el}</Suspense>} />
                    ),
                  )}
                </Route>
              </Routes>
            </RealtimeProvider>
          </HashRouter>
        </QueryClientProvider>
      </DatesProvider>
    </MantineProvider>
  );
}

/** Strona startowa to statystyki (zakres dat z URL zostaje). */
function ToStatistics() {
  const { search } = useLocation();
  return <Navigate to={{ pathname: '/statistics', search }} replace />;
}
