import { Alert, Button, Center, Loader } from '@mantine/core';

export function Loading() {
  return (
    <Center py="xl">
      <Loader size="sm" />
    </Center>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : 'Nieznany błąd';
  return (
    <Alert color="red" title="Nie udało się pobrać danych" my="md">
      {message}. Sprawdź, czy API działa, i spróbuj ponownie.
      {onRetry && (
        <Button size="xs" variant="light" color="red" ml="sm" onClick={onRetry}>
          Ponów
        </Button>
      )}
    </Alert>
  );
}
