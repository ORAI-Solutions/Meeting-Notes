 
import { Box, Button, Flex, HStack, IconButton, useColorMode, useToast, Checkbox, Progress } from '@chakra-ui/react';
import axios from 'axios';
import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { FiSettings, FiMoon, FiSun } from 'react-icons/fi';
import Sidebar from './Sidebar';
import MeetingDetail from './MeetingDetail';
import { Modal, ModalOverlay, ModalContent, ModalHeader, ModalBody, ModalFooter } from '@chakra-ui/react';

function MainApp() {
  const toast = useToast();
  const navigate = useNavigate();
  const { colorMode, toggleColorMode } = useColorMode();
  const queryClient = useQueryClient();
  const [meetingId, setMeetingId] = useState<string | null>(null);
  const [inputs, setInputs] = useState<{ id: string; name: string }[]>([]);
  const [outputs, setOutputs] = useState<{ id: string; name: string }[]>([]);
  const [micId, setMicId] = useState<string | undefined>();
  const [outId, setOutId] = useState<string | undefined>();
  const [selectedMeetingId, setSelectedMeetingId] = useState<string | null>(null);
  const [wipeDb, setWipeDb] = useState<boolean>(true);
  const [wipeAudio, setWipeAudio] = useState<boolean>(true);
  const [isWiping, setIsWiping] = useState<boolean>(false);
  // LLM settings + summary UI state
  const [llmModelPath, setLlmModelPath] = useState<string>('');
  const [llmDevice, setLlmDevice] = useState<'auto' | 'cpu' | 'gpu'>('auto');
  const [llmLocalModels, setLlmLocalModels] = useState<string[]>([]);
  const [llmPresetList, setLlmPresetList] = useState<Array<{ id: string; label: string; filename: string }>>([]);
  const [llmAllPresets, setLlmAllPresets] = useState<Array<{ id: string; label: string; filename: string }>>([]);
  const [llmGpuAvailable, setLlmGpuAvailable] = useState<boolean>(false);
  const [isSavingSettings, setIsSavingSettings] = useState<boolean>(false);
  const [isDownloading, setIsDownloading] = useState<boolean>(false);
  const [downloadProgress, setDownloadProgress] = useState<number>(0);
  const [isSummarizing] = useState<boolean>(false);
  const [summaryProgress] = useState<number>(0);
  const [summaryPhase] = useState<string>('');
  
  const [showAsrModal, setShowAsrModal] = useState(false);
  const [asrDownloading, setAsrDownloading] = useState(false);
  const [asrProgress, setAsrProgress] = useState(0);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await axios.get('/devices');
        const ins = res.data.inputs || [];
        const outs = res.data.outputs || [];
        setInputs(ins);
        setOutputs(outs);
        const defIn = ins.find((d: any) => d.is_default);
        const defOut = outs.find((d: any) => d.is_default);
        if (defIn) setMicId(defIn.id);
        if (defOut) setOutId(defOut.id);
      } catch (error) {
        console.error('Failed to load devices', error);
      }
    };
    load();
  }, []);

  // Load settings on mount
  useEffect(() => {
    const loadSettings = async () => {
      try {
        const res = await axios.get('/settings');
        if (res.data.llm) {
          setLlmModelPath(res.data.llm.model_path || '');
          setLlmDevice(res.data.llm.device || 'auto');
        }
      } catch (error) {
        console.error('Failed to load settings:', error);
      }
    };
    loadSettings();
  }, []);

  // Load LLM options on mount
  useEffect(() => {
    const loadLlmOptions = async () => {
      try {
        const res = await axios.get('/settings/llm/options');
        setLlmLocalModels(res.data.models || []);
        const presets = res.data.presets || [];
        setLlmAllPresets(presets);
        setLlmGpuAvailable(res.data.gpu_available || false);
        // Hide already-downloaded presets from "Download" list
        const localFilenames = (res.data.models || []).map((p: string) => {
          const parts = p.split('\\');
          return parts[parts.length - 1];
        });
        const notDownloaded = presets.filter((p: any) => !localFilenames.includes(p.filename));
        setLlmPresetList(notDownloaded);
      } catch (error) {
        console.error('Failed to load LLM options:', error);
      }
    };
    loadLlmOptions();
  }, [isDownloading]); // Reload after download completes

  // Check ASR model presence and prompt
  useEffect(() => {
    const checkAsr = async () => {
      try {
        const o = await axios.get('/settings/asr/options');
        const present = !!o.data.model_present;
        if (!present) {
          setShowAsrModal(true);
        }
      } catch {}
    };
    checkAsr();
  }, []);

  const startAsrDownload = async () => {
    try {
      setAsrDownloading(true);
      await axios.post('/settings/asr/download', {});
      const poll = async () => {
        const r = await axios.get('/settings/asr/download/status');
        setAsrProgress(r.data.progress || 0);
        if (r.data.status === 'running') {
          setTimeout(poll, 1000);
        } else {
          setAsrDownloading(false);
          setShowAsrModal(false);
        }
      };
      setTimeout(poll, 1000);
    } catch (e) {
      setAsrDownloading(false);
      toast({ title: 'ASR download failed', status: 'error', duration: 3000 });
    }
  };

  const startRecording = async () => {
    try {
      const res = await axios.post('/meetings/start', {
        title: 'Meeting ' + new Date().toLocaleString(),
        mic_device_id: micId,
        output_device_id: outId,
      });
      if (res.data.meeting_id) {
        setMeetingId(String(res.data.meeting_id));
        toast({
          title: 'Recording started',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
        queryClient.invalidateQueries({ queryKey: ['meetings'] });
      }
    } catch (error) {
      console.error('Failed to start recording', error);
      toast({
        title: 'Failed to start recording',
        description: axios.isAxiosError(error) ? error.response?.data?.error : 'Unknown error',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  const stopRecording = async () => {
    if (!meetingId) return;
    try {
      await axios.post(`/meetings/${meetingId}/stop`);
      toast({
        title: 'Recording stopped',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
      setMeetingId(null);
      queryClient.invalidateQueries({ queryKey: ['meetings'] });
    } catch (error) {
      console.error('Failed to stop recording', error);
      toast({
        title: 'Failed to stop recording',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  const { data: meetings, isLoading: isLoadingMeetings } = useQuery({
    queryKey: ['meetings'],
    queryFn: async () => {
      const res = await axios.get('/meetings');
      return res.data || [];
    },
    refetchInterval: meetingId ? 5000 : false,
  });

  const { data: meetingDetail } = useQuery({
    queryKey: ['meeting', selectedMeetingId],
    queryFn: async () => {
      if (!selectedMeetingId) return null;
      const res = await axios.get(`/meetings/${selectedMeetingId}`);
      return res.data;
    },
    enabled: !!selectedMeetingId,
    refetchInterval: false,
  });

  const startTranscription = async () => {};

  const startSummarization = async () => {};

  return (
    <Box minH="100vh" bg={colorMode === 'dark' ? 'gray.900' : 'gray.50'}>
      {/* Top bar */}
      <Box
        h="50px"
        bg={colorMode === 'dark' ? 'gray.800' : 'white'}
        borderBottom="1px"
        borderBottomColor={colorMode === 'dark' ? 'gray.700' : 'gray.200'}
        px={4}
        display="flex"
        alignItems="center"
        justifyContent="space-between"
      >
        <HStack spacing={3}>
          <Box fontSize="xl">🎙️</Box>
          <Box fontWeight="bold" fontSize="lg">Meeting Notes</Box>
        </HStack>
        
        <HStack spacing={2}>
          <Button
            leftIcon={<FiSettings />}
            variant="ghost"
            size="sm"
            onClick={() => navigate('/settings')}
          >
            Settings
          </Button>
          <IconButton
            aria-label="Toggle color mode"
            icon={colorMode === 'light' ? <FiMoon /> : <FiSun />}
            onClick={toggleColorMode}
            variant="ghost"
            size="sm"
          />
        </HStack>
      </Box>

      {/* Main layout */}
      <Flex h="calc(100vh - 50px)">
        {/* Sidebar */}
        <Sidebar
          meetingId={meetingId}
          meetings={meetings || []}
          selectedMeetingId={selectedMeetingId}
          onSelectMeeting={setSelectedMeetingId}
          onStartRecording={startRecording}
          onStopRecording={stopRecording}
          isLoadingMeetings={isLoadingMeetings}
          inputs={inputs}
          outputs={outputs}
          micId={micId}
          outId={outId}
          onMicChange={setMicId}
          onOutChange={setOutId}
        />

        {/* Main content */}
        <MeetingDetail meeting={meetingDetail} />
      </Flex>

      {/* ASR First-Run Modal */}
      <Modal isOpen={showAsrModal} onClose={() => setShowAsrModal(false)} isCentered>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>ASR Model Required</ModalHeader>
          <ModalBody>
            This app needs a local Whisper model to transcribe audio. Download now?
            
            {asrDownloading && (
              <Box mt={3}>
                <Progress value={Math.round(asrProgress * 100)} size="sm" />
              </Box>
            )}
          </ModalBody>
          <ModalFooter>
            <HStack>
              <Button variant="ghost" onClick={() => setShowAsrModal(false)}>Later</Button>
              <Button colorScheme="blue" onClick={startAsrDownload} isLoading={asrDownloading}>Download</Button>
            </HStack>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
}

export default MainApp;
