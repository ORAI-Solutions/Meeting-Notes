import { Box, VStack, HStack, Text, Badge } from '@chakra-ui/react';

interface Segment {
  id?: number;
  t_start_ms: number;
  t_end_ms: number;
  speaker: string;
  text: string;
  confidence?: number | null;
}

export default function TranscriptViewer({ segments }: { segments: Segment[] }) {
  return (
    <Box p={4} overflowY="auto" h="100%">
      <VStack align="stretch" spacing={3}>
        {(segments || []).map((s, idx) => (
          <Box key={s.id || idx} p={3} borderWidth={1} borderRadius="md">
            <HStack justify="space-between" mb={1}>
              <HStack>
                <Badge>{s.speaker || 'Speaker'}</Badge>
                <Text fontSize="sm" color="gray.500">
                  {formatMs(s.t_start_ms)} - {formatMs(s.t_end_ms)}
                </Text>
              </HStack>
              {typeof s.confidence === 'number' && (
                <Badge colorScheme={badgeColor(s.confidence)}>{badgeLabel(s.confidence)}</Badge>
              )}
            </HStack>
            <Text whiteSpace="pre-wrap">{s.text}</Text>
          </Box>
        ))}
      </VStack>
    </Box>
  );
}

function formatMs(ms: number): string {
  const sec = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (h > 0) return `${h}:${pad2(m)}:${pad2(s)}`;
  return `${m}:${pad2(s)}`;
}

function pad2(n: number): string { return n < 10 ? `0${n}` : String(n); }


function badgeColor(c: number): string {
  if (c >= 0.75) return 'green';
  if (c >= 0.5) return 'yellow';
  return 'red';
}

function badgeLabel(c: number): string {
  if (c >= 0.75) return `High ${c.toFixed(2)}`;
  if (c >= 0.5) return `Medium ${c.toFixed(2)}`;
  return `Low ${c.toFixed(2)}`;
}


