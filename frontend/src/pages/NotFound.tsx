import { Anchor, Stack, Text, Title } from '@mantine/core';
import { Link } from 'react-router-dom';

export function NotFound() {
  return (
    <Stack align="flex-start" py="xl">
      <Title order={2}>Nie ma takiej strony</Title>
      <Text size="sm">
        <Anchor component={Link} to="/">
          Wróć do wyników
        </Anchor>
      </Text>
    </Stack>
  );
}
