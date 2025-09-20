import {
  Box,
  Grid,
  VStack,
  HStack,
  Text,
  Heading,
  Button,
  ButtonGroup,
  useColorMode,
  Progress,
  Divider,
  Badge,
  Checkbox,
  Stack,
  useToast,
  Input,
  IconButton,
  List,
  ListItem,
} from '@chakra-ui/react';
 
import { FiFileText, FiBookOpen, FiEdit2, FiCheck, FiX, FiMic, FiColumns } from 'react-icons/fi';
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import TranscriptViewer from './TranscriptViewer';
import axios from 'axios';
import { useQueryClient } from '@tanstack/react-query';
import Markdown from './Markdown';

interface MeetingDetailProps {
  meeting: any;
}

export default function MeetingDetail({
  meeting,
}: MeetingDetailProps) {
  const { colorMode } = useColorMode();
  const toast = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editTitle, setEditTitle] = useState('');
  const [highlightTimestamp, setHighlightTimestamp] = useState<number | null>(null);
  const [highlightSegmentId, setHighlightSegmentId] = useState<number | null>(null);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [txStatus, setTxStatus] = useState<{ status: string; progress: number; message?: string } | null>(null);
  const [isSummarizing, setIsSummarizing] = useState(false);
  const [sumMsg, setSumMsg] = useState<string>('');
  const [summaryLength, setSummaryLength] = useState<'short' | 'mid' | 'long'>('mid');
  const [viewMode, setViewMode] = useState<'transcript' | 'summary' | 'split'>(
    () => (meeting?.summary ? 'split' : 'transcript')
  );

  const toggleActionItem = async (itemId: string, currentStatus: string) => {
    toast({ title: 'Action item update not yet implemented', status: 'info', duration: 3000 });
  };

  const startEditingTitle = () => {
    setEditTitle(meetingData.title || `Meeting #${meetingId}`);
    setIsEditingTitle(true);
  };

  const cancelEditingTitle = () => {
    setIsEditingTitle(false);
    setEditTitle('');
  };

  const updateMeetingTitle = async () => {
    if (!editTitle.trim()) {
      toast({
        title: 'Title cannot be empty',
        status: 'error',
        duration: 3000,
      });
      return;
    }

    try {
      await axios.put(`/meetings/${meetingId}`, {
        title: editTitle.trim(),
      });
      
      // Invalidate and refetch the meeting data and meetings list
      queryClient.invalidateQueries({ queryKey: ['meeting', meetingId] });
      queryClient.invalidateQueries({ queryKey: ['meetings'] });
      
      toast({
        title: 'Meeting title updated',
        status: 'success',
        duration: 3000,
      });
      setIsEditingTitle(false);
      setEditTitle('');
    } catch (error) {
      console.error('Error updating meeting title:', error);
      toast({
        title: 'Failed to update meeting title',
        status: 'error',
        duration: 3000,
      });
    }
  };

  const startTranscription = async () => {
    if (!meetingId) return;
    // Ensure ASR model present
    try {
      const o = await axios.get('/settings/asr/options');
      const present = !!o.data?.model_present;
      if (!present) {
        toast({
          title: 'ASR‑Modell erforderlich',
          description: 'Bitte lade ein Whisper‑Modell unter Einstellungen herunter.',
          status: 'warning',
          duration: 4000,
        });
        navigate('/settings');
        return;
      }
    } catch {
      toast({ title: 'Modellprüfung fehlgeschlagen', status: 'error', duration: 4000 });
      return;
    }
    try {
      setIsTranscribing(true);
      setTxStatus({ status: 'running', progress: 0 });
      await axios.post(`/meetings/${meetingId}/transcribe`, {});
      // Poll status a few times
      const poll = async () => {
        try {
          const res = await axios.get(`/meetings/${meetingId}/transcribe/status`);
          setTxStatus(res.data);
          if (res.data.status === 'running') {
            setTimeout(poll, 1500);
          } else {
            setIsTranscribing(false);
            if (res.data.status === 'done') {
              await queryClient.invalidateQueries({ queryKey: ['meeting', meetingId] });
            }
          }
        } catch (e) {
          setIsTranscribing(false);
        }
      };
      setTimeout(poll, 1500);
    } catch (error) {
      setIsTranscribing(false);
      toast({ title: 'Failed to start transcription', status: 'error', duration: 3000 });
    }
  };

  const startSummarization = async () => {
    if (!meetingId) return;
    // Ensure LLM model present
    try {
      const [optRes, settingsRes] = await Promise.all([
        axios.get('/settings/llm/options'),
        axios.get('/settings'),
      ]);
      const models = Array.isArray(optRes.data?.models) ? optRes.data.models : [];
      const configuredPath = !!(settingsRes.data?.llm && settingsRes.data.llm.model_path);
      const present = models.length > 0 || configuredPath;
      if (!present) {
        toast({
          title: 'LLM‑Modell erforderlich',
          description: 'Bitte wähle ein GGUF‑Modell in den Einstellungen oder lade eines herunter.',
          status: 'warning',
          duration: 4000,
        });
        navigate('/settings');
        return;
      }
    } catch {
      toast({ title: 'Modellprüfung fehlgeschlagen', status: 'error', duration: 4000 });
      return;
    }
    try {
      setIsSummarizing(true);
      setSumMsg('Starting summarization...');
      await axios.post(`/meetings/${meetingId}/summarize`, { length: summaryLength });
      setSumMsg('Saving summary...');
      // reload meeting detail to fetch summary
      await queryClient.invalidateQueries({ queryKey: ['meeting', meetingId] });
      setIsSummarizing(false);
      setSumMsg('');
      toast({ title: 'Summary created', status: 'success', duration: 2000 });
    } catch (e) {
      setIsSummarizing(false);
      setSumMsg('');
      toast({ title: 'Failed to summarize', status: 'error', duration: 3000 });
    }
  };

  
  const meetingData = meeting?.meeting || meeting;
  const meetingId = meetingData?.id;
  const transcriptSegments = meeting?.transcript_segments || [];
  const summary = meeting?.summary || null;

  useEffect(() => {
    if (summary && viewMode === 'transcript') {
      setViewMode('split');
    }
  }, [summary]);


  if (!meeting || !meetingId) {
    return (
      <Box
        flex="1"
        display="flex"
        alignItems="center"
        justifyContent="center"
        color="gray.500"
      >
        <VStack spacing={3}>
          <Text fontSize="lg">Select a meeting to view details</Text>
          <Text fontSize="sm">Your meetings will appear in the sidebar</Text>
        </VStack>
      </Box>
    );
  }

  return (
    <Box flex="1" display="flex" flexDirection="column" h="100%" overflow="hidden">
      {/* Header */}
      <Box
        p={4}
        borderBottom="1px"
        borderBottomColor={colorMode === 'dark' ? 'gray.700' : 'gray.200'}
        bg={colorMode === 'dark' ? 'gray.800' : 'white'}
      >
        <HStack justify="space-between">
          <VStack align="start" spacing={1} flex="1">
            <HStack spacing={2} align="center" width="100%">
              {isEditingTitle ? (
                <>
                  <IconButton
                    size="sm"
                    icon={<FiCheck />}
                    aria-label="Save"
                    colorScheme="green"
                    onClick={updateMeetingTitle}
                  />
                  <IconButton
                    size="sm"
                    icon={<FiX />}
                    aria-label="Cancel"
                    colorScheme="red"
                    onClick={cancelEditingTitle}
                  />
                  <Input
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    fontSize="lg"
                    fontWeight="semibold"
                    variant="outline"
                    bg={colorMode === 'dark' ? 'gray.700' : 'white'}
                    borderColor={colorMode === 'dark' ? 'gray.600' : 'gray.300'}
                    _focus={{ 
                      borderColor: 'blue.500',
                      boxShadow: '0 0 0 1px blue.500'
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        updateMeetingTitle();
                      } else if (e.key === 'Escape') {
                        cancelEditingTitle();
                      }
                    }}
                    autoFocus
                  />
                </>
              ) : (
                <>
                  <IconButton
                    size="sm"
                    icon={<FiEdit2 />}
                    aria-label="Edit title"
                    variant="ghost"
                    opacity={0.7}
                    _hover={{ opacity: 1 }}
                    onClick={startEditingTitle}
                  />
                  <Heading 
                    size="md"
                    py={1}
                    px={2}
                    borderRadius="md"
                    cursor="pointer"
                    _hover={{ bg: colorMode === 'dark' ? 'gray.700' : 'gray.100' }}
                    onClick={startEditingTitle}
                  >
                    {meetingData.title || `Meeting #${meetingId}`}
                  </Heading>
                </>
              )}
            </HStack>
            <Text fontSize="sm" color="gray.500">
              {new Date(meetingData.started_at).toLocaleString()}
              {meetingData.ended_at && ` - ${new Date(meetingData.ended_at).toLocaleTimeString()}`}
            </Text>
          </VStack>
          
          <HStack spacing={2}>
            <ButtonGroup size="sm" isAttached variant="outline" alignSelf="end">
              <Button
                leftIcon={<FiFileText />}
                variant={viewMode === 'transcript' ? 'solid' : 'outline'}
                onClick={() => setViewMode('transcript')}
              >
                Transcript
              </Button>
              <Button
                leftIcon={<FiBookOpen />}
                variant={viewMode === 'summary' ? 'solid' : 'outline'}
                onClick={() => setViewMode('summary')}
              >
                Summary
              </Button>
              <Button
                leftIcon={<FiColumns />}
                variant={viewMode === 'split' ? 'solid' : 'outline'}
                onClick={() => setViewMode('split')}
              >
                Split
              </Button>
            </ButtonGroup>

            <Button alignSelf="end" size="sm" leftIcon={<FiMic />} onClick={startTranscription} isLoading={isTranscribing}>
              Transcribe
            </Button>
            <VStack align="start" justifyItems="end">
              <Text fontSize="xs" color="gray.500">Summary Length</Text>
              <ButtonGroup size="sm" isAttached variant="outline">
                <Button
                  variant={summaryLength === 'short' ? 'solid' : 'outline'}
                  onClick={() => setSummaryLength('short')}
                >
                  Short
                </Button>
                <Button
                  variant={summaryLength === 'mid' ? 'solid' : 'outline'}
                  onClick={() => setSummaryLength('mid')}
                >
                  Mid
                </Button>
                <Button
                  variant={summaryLength === 'long' ? 'solid' : 'outline'}
                  onClick={() => setSummaryLength('long')}
                >
                  Long
                </Button>
              </ButtonGroup>
            </VStack>
            <Button alignSelf="end" size="sm" leftIcon={<FiBookOpen />} onClick={startSummarization} isLoading={isSummarizing}>
              Summarize
            </Button>
          </HStack>
        </HStack>
      </Box>
      
      {txStatus && (
        <Box px={4} py={2}>
          <HStack>
            <Text fontSize="sm">Transcription: {txStatus.status}</Text>
            {typeof txStatus.progress === 'number' && (
              <Progress value={Math.round(txStatus.progress * 100)} size="xs" flex="1" />
            )}
            {txStatus.message && (
              <Badge colorScheme={txStatus.status === 'error' ? 'red' : 'blue'}>{txStatus.message}</Badge>
            )}
          </HStack>
        </Box>
      )}
      {isSummarizing && (
        <Box px={4} py={2}>
          <HStack>
            <Text fontSize="sm">Summarization running...</Text>
            {sumMsg && <Badge colorScheme="blue">{sumMsg}</Badge>}
          </HStack>
        </Box>
      )}

      <Box flex="1" overflow="hidden">
        {viewMode === 'transcript' && (
          <TranscriptViewer segments={transcriptSegments} />
        )}

        {viewMode === 'summary' && (
          <Box px={4} py={3} h="100%" overflowY="auto">
            <VStack align="stretch" spacing={3}>
              <Heading size="sm">Summary</Heading>
              {summary ? (
                <>
                  {summary.abstract_md && (
                    <Box>
                      <Heading size="xs" mb={1}>Abstract</Heading>
                      <Box className="markdown-body">
                        <Markdown>{String(summary.abstract_md)}</Markdown>
                      </Box>
                    </Box>
                  )}
                  {summary.bullets_md && (
                    <Box>
                      <Heading size="xs" mb={1}>Key points</Heading>
                      <Box className="markdown-body">
                        <Markdown>{String(summary.bullets_md)}</Markdown>
                      </Box>
                    </Box>
                  )}
                </>
              ) : (
                <VStack align="center" justify="center" spacing={1} color="gray.500" py={10}>
                  <Text>No summary yet.</Text>
                  <Text fontSize="sm">Click "Summarize" to generate one.</Text>
                </VStack>
              )}
            </VStack>
          </Box>
        )}

        {viewMode === 'split' && (
          <Grid templateColumns="1fr 1fr" gap={4} h="100%" p={4} overflow="hidden">
            <Box overflowY="auto">
              <TranscriptViewer segments={transcriptSegments} />
            </Box>
            <Box overflowY="auto">
              <VStack align="stretch" spacing={3}>
                <Heading size="sm">Summary</Heading>
                {summary ? (
                  <>
                    {summary.abstract_md && (
                      <Box>
                        <Heading size="xs" mb={1}>Abstract</Heading>
                        <Box className="markdown-body">
                          <Markdown>{String(summary.abstract_md)}</Markdown>
                        </Box>
                      </Box>
                    )}
                    {summary.bullets_md && (
                      <Box>
                        <Heading size="xs" mb={1}>Key points</Heading>
                        <Box className="markdown-body">
                          <Markdown>{String(summary.bullets_md)}</Markdown>
                        </Box>
                      </Box>
                    )}
                  </>
                ) : (
                  <VStack align="center" justify="center" spacing={1} color="gray.500" py={10}>
                    <Text>No summary yet.</Text>
                    <Text fontSize="sm">Click "Summarize" to generate one.</Text>
                  </VStack>
                )}
              </VStack>
            </Box>
          </Grid>
        )}
      </Box>
    </Box>
  );
}
