import {
  Box,
  Button,
  Container,
  FormControl,
  FormLabel,
  FormHelperText,
  Heading,
  Select,
  Tab,
  TabList,
  TabPanel,
  TabPanels,
  Tabs,
  VStack,
  HStack,
  Text,
  useToast,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Checkbox,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  useDisclosure,
  Icon,
  Spacer,
  useColorModeValue,
  Progress,
} from '@chakra-ui/react';
import { FiSettings, FiMic, FiAlertTriangle, FiTrash2, FiArrowLeft, FiKey, FiRefreshCw, FiDownload } from 'react-icons/fi';
import { useState, useEffect, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { useDownload } from '../context/DownloadContext';

interface Device {
  id: string;
  name: string;
  is_default?: boolean;
}

export const Settings = () => {
  const { llm, asr, startLlmDownload: startLlmDlGlobal, startAsrDownload: startAsrDlGlobal, refresh: refreshDownloads } = useDownload();
  const toast = useToast();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const { isOpen: isWipeOpen, onOpen: onWipeOpen, onClose: onWipeClose } = useDisclosure();

  // Audio devices
  const [inputs, setInputs] = useState<Device[]>([]);
  const [outputs, setOutputs] = useState<Device[]>([]);
  const [selectedInput, setSelectedInput] = useState<string>('');
  const [selectedOutput, setSelectedOutput] = useState<string>('');
  const [devicesLoading, setDevicesLoading] = useState<boolean>(false);

  // Danger zone
  const [wipeDb, setWipeDb] = useState(true);
  const [wipeAudio, setWipeAudio] = useState(true);
  const [wiping, setWiping] = useState(false);

  // Tabs
  const [tabIndex, setTabIndex] = useState(0);
  useEffect(() => {
    const t = searchParams.get('tab');
    if (t === 'license') setTabIndex(3); // License is now the fourth tab (after Audio, LLM, GPU Runtime)
  }, [searchParams]);

  useEffect(() => {
    loadDevices();
  }, []);

  // ASR options
  const [asrMode, setAsrMode] = useState<'fast'|'accurate'>('fast');
  const [asrDevice, setAsrDevice] = useState<'auto'|'cpu'|'cuda'>('auto');
  const [asrLanguage, setAsrLanguage] = useState<string>('');
  const [asrModelPresent, setAsrModelPresent] = useState<boolean>(false);
  const [asrPresets, setAsrPresets] = useState<Array<{id:string;label:string;size_bytes?:number}>>([]);
  const [asrModelPath, setAsrModelPath] = useState<string>('');
  const [asrDownloading, setAsrDownloading] = useState<boolean>(false);
  const [asrProgress, setAsrProgress] = useState<number>(0);
  const [asrMessage, setAsrMessage] = useState<string>('');

  // LLM options
  const [llmGpuAvailable, setLlmGpuAvailable] = useState<boolean>(false);
  const [llmLocalModels, setLlmLocalModels] = useState<string[]>([]);
  const [llmPresets, setLlmPresets] = useState<Array<{id:string;label:string;filename:string}>>([]);
  const [llmSelectedPreset, setLlmSelectedPreset] = useState<string>('');
  const [llmDevice, setLlmDevice] = useState<'auto'|'cpu'|'cuda'>('auto');
  const [llmDownloading, setLlmDownloading] = useState<boolean>(false);
  const [llmProgress, setLlmProgress] = useState<number>(0);
  const [llmMessage, setLlmMessage] = useState<string>('');

  // CUDA Runtime options
  const [cudaStatus, setCudaStatus] = useState<{
    installed_libraries: Record<string, boolean>;
    is_downloading: boolean;
    current_download: string | null;
    download_progress: Record<string, number>;
    error_message: string | null;
    cuda_directory: string;
    whisper_gpu_ready: boolean;
    llama_gpu_ready: boolean;
  } | null>(null);
  const [cudaDownloading, setCudaDownloading] = useState<boolean>(false);

  // Derive installed filenames from absolute paths
  const llmInstalledSet = useMemo(() => {
    const set = new Set<string>();
    for (const p of llmLocalModels) {
      const parts = p.split('\\');
      set.add(parts[parts.length - 1] || p);
    }
    return set;
  }, [llmLocalModels]);

  const loadDevices = async () => {
    setDevicesLoading(true);
    try {
      const res = await axios.get('/devices');
      setInputs(res.data.inputs || []);
      setOutputs(res.data.outputs || []);

      const defaultInput = res.data.inputs?.find((d: Device) => d.is_default);
      const defaultOutput = res.data.outputs?.find((d: Device) => d.is_default);
      if (defaultInput) setSelectedInput(defaultInput.id);
      if (defaultOutput) setSelectedOutput(defaultOutput.id);
    } catch (error) {
      console.error('Failed to load devices:', error);
      toast({ title: 'Failed to load devices', status: 'error', duration: 3000 });
    } finally {
      setDevicesLoading(false);
    }
  };

  const loadAsrSettingsAndOptions = async () => {
    try {
      const s = await axios.get('/settings');
      const asr = s.data.asr || {};
      setAsrMode(asr.mode || 'fast');
      setAsrDevice(asr.device || 'auto');
      setAsrLanguage(asr.language || '');
    } catch {}
    try {
      const o = await axios.get('/settings/asr/options');
      setAsrModelPresent(!!o.data.model_present);
      setAsrModelPath(o.data.model_path || '');
      setAsrPresets(o.data.presets || []);
    } catch {}
  };

  useEffect(() => {
    loadAsrSettingsAndOptions();
  }, []);

  const loadLlmOptions = async () => {
    try {
      const res = await axios.get('/settings/llm/options');
      setLlmGpuAvailable(!!res.data.gpu_available);
      setLlmLocalModels(res.data.models || []);
      setLlmPresets(res.data.presets || []);
      // Load persisted LLM settings to prefill device and preset
      try {
        const s = await axios.get('/settings');
        const dev = (s.data.llm_device || 'auto') as 'auto'|'cpu'|'cuda';
        setLlmDevice(dev);
        const savedPreset = s.data.llm?.model_id as string | undefined;
        if (savedPreset) {
          setLlmSelectedPreset(savedPreset);
        } else if (!llmSelectedPreset && res.data.presets && res.data.presets.length > 0) {
          setLlmSelectedPreset(res.data.presets[0].id);
        }
      } catch {}
    } catch (e) {
      
    }
  };

  useEffect(() => {
    loadLlmOptions();
  }, []);

  // Auto-resume download progress from global state on mount and whenever global changes
  useEffect(() => {
    // Initial refresh to get current backend state
    refreshDownloads().catch(() => {});
  }, []);

  useEffect(() => {
    // Mirror global state into local UI flags for LLM
    if (llm.status === 'running') {
      setLlmDownloading(true);
    } else {
      setLlmDownloading(false);
    }
    setLlmProgress(llm.progress || 0);
    setLlmMessage(llm.message || '');
  }, [llm.status, llm.progress, llm.message]);

  useEffect(() => {
    // Mirror global state into local UI flags for ASR
    if (asr.status === 'running') {
      setAsrDownloading(true);
    } else {
      setAsrDownloading(false);
    }
    setAsrProgress(asr.progress || 0);
    setAsrMessage(asr.message || '');
  }, [asr.status, asr.progress, asr.message]);

  // CUDA Runtime Functions
  const loadCudaStatus = async () => {
    try {
      const res = await axios.get('/settings/cuda/status');
      setCudaStatus(res.data);
    } catch (e) {
      console.error('Failed to load CUDA status:', e);
    }
  };

  useEffect(() => {
    loadCudaStatus();
    // Poll status every 5 seconds if downloading
    const interval = setInterval(() => {
      if (cudaStatus?.is_downloading) {
        loadCudaStatus();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [cudaStatus?.is_downloading]);

  const downloadCudaLibraries = async (feature: 'whisper_gpu' | 'llama_gpu') => {
    try {
      setCudaDownloading(true);
      const res = await axios.post('/settings/cuda/download', { feature });
      if (res.data.success) {
        toast({ 
          title: 'CUDA Download Started', 
          description: `Downloading ${res.data.download_size_mb?.toFixed(0) || '?'} MB of CUDA libraries`,
          status: 'info', 
          duration: 5000 
        });
        // Start polling for status
        const pollInterval = setInterval(async () => {
          await loadCudaStatus();
          const status = cudaStatus;
          if (status && !status.is_downloading) {
            clearInterval(pollInterval);
            setCudaDownloading(false);
            if (status.error_message) {
              toast({ 
                title: 'CUDA Download Failed', 
                description: status.error_message,
                status: 'error', 
                duration: 5000 
              });
            } else {
              toast({ 
                title: 'CUDA Libraries Installed', 
                description: `GPU acceleration is now available for ${feature === 'whisper_gpu' ? 'transcription' : 'summarization'}`,
                status: 'success', 
                duration: 5000 
              });
            }
          }
        }, 2000);
      }
    } catch (e) {
      setCudaDownloading(false);
      toast({ title: 'Failed to start CUDA download', status: 'error', duration: 3000 });
    }
  };

  const cleanupCudaLibraries = async () => {
    try {
      const res = await axios.post('/settings/cuda/cleanup');
      if (res.data.success) {
        toast({ title: 'CUDA libraries removed', status: 'success', duration: 3000 });
        await loadCudaStatus();
      }
    } catch (e) {
      toast({ title: 'Failed to cleanup CUDA libraries', status: 'error', duration: 3000 });
    }
  };

  const startLlmDownload = async () => {
    try {
      setLlmDownloading(true);
      setLlmProgress(0);
      await startLlmDlGlobal(llmSelectedPreset || undefined);
      // load options will be refreshed when status becomes done
      const finishWatcher = async () => {
        try {
          const r = await axios.get('/settings/llm/download/status');
          if (r.data.status === 'running') {
            setTimeout(finishWatcher, 1000);
          } else {
            setLlmDownloading(false);
            await loadLlmOptions();
          }
        } catch {
          setTimeout(finishWatcher, 1500);
        }
      };
      setTimeout(finishWatcher, 500);
    } catch (e) {
      setLlmDownloading(false);
      toast({ title: 'LLM download failed', status: 'error', duration: 3000 });
    }
  };

  const saveLlm = async () => {
    try {
      await axios.post('/settings', {
        llm_device: llmDevice,
        llm: { model_id: llmSelectedPreset || null },
      });
      toast({ title: 'LLM settings saved', status: 'success', duration: 2000 });
    } catch (e) {
      toast({ title: 'Failed to save LLM settings', status: 'error', duration: 3000 });
    }
  };

  const saveAsr = async () => {
    try {
      await axios.post('/settings', {
        asr: {
          mode: asrMode,
          device: asrDevice,
          language: asrLanguage || null,
          
        },
      });
      toast({ title: 'ASR settings saved', status: 'success', duration: 2000 });
    } catch (e) {
      toast({ title: 'Failed to save ASR settings', status: 'error', duration: 3000 });
    }
  };

  const startAsrDownload = async (presetId?: string) => {
    try {
      setAsrDownloading(true);
      setAsrProgress(0);
      await startAsrDlGlobal(presetId);
      const finishWatcher = async () => {
        try {
          const r = await axios.get('/settings/asr/download/status');
          if (r.data.status === 'running') {
            setTimeout(finishWatcher, 1000);
          } else {
            setAsrDownloading(false);
            await loadAsrSettingsAndOptions();
          }
        } catch {
          setTimeout(finishWatcher, 1500);
        }
      };
      setTimeout(finishWatcher, 500);
    } catch (e) {
      setAsrDownloading(false);
      toast({ title: 'ASR download failed', status: 'error', duration: 3000 });
    }
  };

  const wipeData = async () => {
    setWiping(true);
    try {
      const res = await axios.post('/settings/wipe', {
        wipe_db: wipeDb,
        wipe_audio: wipeAudio,
      });
      if (res.data.ok) {
        toast({
          title: 'Data wiped successfully',
          description: `${wipeDb ? 'Database cleared. ' : ''}${wipeAudio ? 'Audio files deleted.' : ''}`,
          status: 'success',
          duration: 5000,
        });
      } else {
        toast({ title: 'Partial wipe', description: 'Some data could not be deleted', status: 'warning', duration: 5000 });
      }
      onWipeClose();
    } catch (error) {
      toast({ title: 'Failed to wipe data', status: 'error', duration: 3000 });
    } finally {
      setWiping(false);
    }
  };

  return (
    <Container maxW="container.xl" py={8}>
      <VStack spacing={6} align="stretch">
        <HStack>
          <Button leftIcon={<FiArrowLeft />} variant="ghost" onClick={() => navigate('/')}>Back</Button>
          <Icon as={FiSettings} boxSize={8} />
          <Heading size="lg">Settings</Heading>
          <Spacer />
        </HStack>

        <Tabs colorScheme="blue" variant="enclosed" index={tabIndex} onChange={(i) => { setTabIndex(i); }}>
          <TabList>
            <Tab><HStack><Icon as={FiMic} /><Text>Audio & ASR</Text></HStack></Tab>
            <Tab><HStack><Icon as={FiKey} /><Text>LLM</Text></HStack></Tab>
            <Tab><HStack><Icon as={FiSettings} /><Text>GPU Runtime</Text></HStack></Tab>
            <Tab><HStack><Icon as={FiAlertTriangle} /><Text color="red.500">Danger Zone</Text></HStack></Tab>
          </TabList>

          <TabPanels>
            {/* Audio Devices + ASR Tab */}
            <TabPanel>
              <VStack spacing={6} align="stretch">
                <Box p={6} bg={bgColor} borderRadius="lg" borderWidth={1} borderColor={borderColor}>
                  <VStack spacing={4} align="stretch">
                    <Heading size="md">Audio Input Devices</Heading>

                    <FormControl>
                      <FormLabel>Microphone</FormLabel>
                      <Select value={selectedInput} onChange={(e) => setSelectedInput(e.target.value)} placeholder="Select microphone">
                        {inputs.map((device) => (
                          <option key={device.id} value={device.id}>
                            {device.name} {device.is_default && '(Default)'}
                          </option>
                        ))}
                      </Select>
                      <FormHelperText>Select the microphone for recording your voice</FormHelperText>
                    </FormControl>

                    <Heading size="md" mt={4}>Audio Output Devices</Heading>

                    <FormControl>
                      <FormLabel>System Audio (Loopback)</FormLabel>
                      <Select value={selectedOutput} onChange={(e) => setSelectedOutput(e.target.value)} placeholder="Select output device">
                        {outputs.map((device) => (
                          <option key={device.id} value={device.id}>
                            {device.name} {device.is_default && '(Default)'}
                          </option>
                        ))}
                      </Select>
                      <FormHelperText>Select the output device to capture system audio from</FormHelperText>
                    </FormControl>

                    <Button leftIcon={<FiRefreshCw />} variant="outline" onClick={loadDevices} isLoading={devicesLoading}>
                      Refresh Devices
                    </Button>
                  </VStack>
                </Box>

                <Box p={6} bg={bgColor} borderRadius="lg" borderWidth={1} borderColor={borderColor}>
                  <VStack spacing={4} align="stretch">
                    <Heading size="md">ASR (Transcription)</Heading>
                    <HStack>
                      <FormControl maxW="220px">
                        <FormLabel>Mode</FormLabel>
                        <Select value={asrMode} onChange={(e) => setAsrMode(e.target.value as any)}>
                          <option value="fast">Fast</option>
                          <option value="accurate">Accurate</option>
                        </Select>
                      </FormControl>
                      <FormControl maxW="220px">
                        <FormLabel>Hardware</FormLabel>
                        <Select value={asrDevice} onChange={(e) => setAsrDevice(e.target.value as any)}>
                          <option value="auto">Auto</option>
                          <option value="cpu">CPU</option>
                          <option value="cuda">GPU</option>
                        </Select>
                      </FormControl>
                      <FormControl maxW="220px">
                        <FormLabel>Language</FormLabel>
                        <Select value={asrLanguage} onChange={(e) => setAsrLanguage(e.target.value)}>
                          <option value="">Auto</option>
                          <option value="en">English</option>
                          <option value="de">Deutsch</option>
                          <option value="fr">Français</option>
                          <option value="es">Español</option>
                          <option value="it">Italiano</option>
                        </Select>
                      </FormControl>
                    </HStack>

                    {/* Removed automatic ASR model download consent checkbox */}

                    <HStack>
                      <Button onClick={saveAsr} colorScheme="blue">Save ASR Settings</Button>
                      <Spacer />
                      <VStack align="end" spacing={1}>
                        <HStack>
                          <Button leftIcon={<FiDownload />} variant="outline" onClick={() => startAsrDownload()} isLoading={asrDownloading} isDisabled={asrModelPresent}>
                            {asrModelPresent ? 'Model Installed' : 'Download Model'}
                          </Button>
                          {!asrModelPresent ? (
                            <Text color="red.400">Model missing</Text>
                          ) : (
                            <Text color="green.400">Installed</Text>
                          )}
                        </HStack>
                        {asrModelPresent && asrModelPath && (
                          <Text fontSize="xs" color="gray.500" maxW="500px" noOfLines={1} title={asrModelPath}>
                            {asrModelPath}
                          </Text>
                        )}
                      </VStack>
                    </HStack>
                    {asrDownloading && (
                      <VStack align="stretch">
                        <Progress value={Math.round(asrProgress * 100)} size="sm" />
                        {asrMessage && <Text fontSize="sm" color="gray.500">{asrMessage}</Text>}
                      </VStack>
                    )}
                  </VStack>
                </Box>
              </VStack>
            </TabPanel>

            {/* LLM Tab */}
            <TabPanel>
              <VStack spacing={6} align="stretch">
                <Box p={6} bg={bgColor} borderRadius="lg" borderWidth={1} borderColor={borderColor}>
                  <VStack spacing={4} align="stretch">
                    <Heading size="md">Local LLM</Heading>
                    <Text fontSize="sm" color="gray.500">GPU available: {llmGpuAvailable ? 'Yes' : 'No'}</Text>

                    <FormControl>
                      <FormLabel>Available Presets</FormLabel>
                      <Select value={llmSelectedPreset} onChange={(e) => setLlmSelectedPreset(e.target.value)}>
                        {llmPresets.map((p) => {
                          const installed = llmInstalledSet.has(p.filename);
                          return (
                            <option key={p.id} value={p.id}>{p.label}{installed ? ' (installed)' : ''}</option>
                          );
                        })}
                      </Select>
                      <FormHelperText>Select a preset to download locally (.gguf)</FormHelperText>
                    </FormControl>

                    <FormControl maxW="220px">
                      <FormLabel>LLM Hardware</FormLabel>
                      <Select value={llmDevice} onChange={(e) => setLlmDevice(e.target.value as any)}>
                        <option value="auto">Auto</option>
                        <option value="cpu">CPU</option>
                        <option value="cuda">GPU</option>
                      </Select>
                      <FormHelperText>Controls GPU offload for summarization</FormHelperText>
                    </FormControl>

                    <HStack>
                      <Button colorScheme="blue" onClick={saveLlm}>Save LLM Settings</Button>
                      <Button
                        leftIcon={<FiDownload />}
                        variant="outline"
                        onClick={startLlmDownload}
                        isLoading={llmDownloading}
                        isDisabled={((): boolean => {
                          const p = llmPresets.find((pp) => pp.id === llmSelectedPreset);
                          return !!(p && llmInstalledSet.has(p.filename));
                        })()}
                      >
                        Download Model
                      </Button>
                      {llmLocalModels.length > 0 && (
                        <Text color="green.400">Installed models: {llmLocalModels.length}</Text>
                      )}
                    </HStack>

                    {llmDownloading && (
                      <VStack align="stretch">
                        <Progress value={Math.round(llmProgress * 100)} size="sm" />
                        {llmMessage && <Text fontSize="sm" color="gray.500">{llmMessage}</Text>}
                      </VStack>
                    )}

                    <Heading size="sm" mt={6}>Installed Models</Heading>
                    {llmLocalModels.length === 0 ? (
                      <Text fontSize="sm" color="gray.500">No models installed yet.</Text>
                    ) : (
                      <VStack align="stretch" spacing={1} maxH="200px" overflowY="auto">
                        {llmLocalModels.map((p) => {
                          const parts = p.split('\\');
                          const name = parts[parts.length - 1] || p;
                          return (
                            <HStack key={p} justify="space-between">
                              <Text fontSize="sm" title={p} noOfLines={1}>{name}</Text>
                              <Text fontSize="xs" color="gray.500">{p}</Text>
                            </HStack>
                          );
                        })}
                      </VStack>
                    )}
                  </VStack>
                </Box>
              </VStack>
            </TabPanel>

            {/* GPU Runtime Tab */}
            <TabPanel>
              <VStack spacing={6} align="stretch">
                <Box p={6} bg={bgColor} borderRadius="lg" borderWidth={1} borderColor={borderColor}>
                  <VStack spacing={4} align="stretch">
                    <Heading size="md">GPU Runtime Management</Heading>
                    <Text fontSize="sm" color="gray.500">
                      Manage CUDA runtime libraries for GPU acceleration. These libraries are downloaded on-demand to reduce the application size.
                    </Text>

                    {cudaStatus && (
                      <>
                        <Alert status={cudaStatus.whisper_gpu_ready && cudaStatus.llama_gpu_ready ? 'success' : 'warning'}>
                          <AlertIcon />
                          <Box>
                            <AlertTitle>GPU Acceleration Status</AlertTitle>
                            <AlertDescription>
                              <VStack align="start" spacing={1}>
                                <Text>Transcription (Whisper): {cudaStatus.whisper_gpu_ready ? '✅ Ready' : '⚠️ Libraries needed'}</Text>
                                <Text>Summarization (LLaMA): {cudaStatus.llama_gpu_ready ? '✅ Ready' : '⚠️ Libraries needed'}</Text>
                              </VStack>
                            </AlertDescription>
                          </Box>
                        </Alert>

                        <Box>
                          <Heading size="sm" mb={2}>CUDA Libraries Status</Heading>
                          <VStack align="stretch" spacing={2}>
                            {Object.entries(cudaStatus.installed_libraries).map(([lib, installed]) => (
                              <HStack key={lib} justify="space-between">
                                <Text fontSize="sm">{lib}</Text>
                                <Text fontSize="sm" color={installed ? 'green.500' : 'gray.500'}>
                                  {installed ? 'Installed' : 'Not installed'}
                                </Text>
                              </HStack>
                            ))}
                          </VStack>
                        </Box>

                        {cudaStatus.is_downloading && cudaStatus.current_download && (
                          <Box>
                            <Text fontSize="sm">Downloading: {cudaStatus.current_download}</Text>
                            <Progress 
                              value={cudaStatus.download_progress[cudaStatus.current_download] || 0} 
                              size="sm" 
                              colorScheme="blue"
                            />
                          </Box>
                        )}

                        {cudaStatus.error_message && (
                          <Alert status="error">
                            <AlertIcon />
                            <AlertDescription>{cudaStatus.error_message}</AlertDescription>
                          </Alert>
                        )}

                        <HStack spacing={3}>
                          {!cudaStatus.whisper_gpu_ready && (
                            <Button
                              leftIcon={<FiDownload />}
                              colorScheme="blue"
                              onClick={() => downloadCudaLibraries('whisper_gpu')}
                              isLoading={cudaDownloading || cudaStatus.is_downloading}
                              size="sm"
                            >
                              Download Whisper GPU Support
                            </Button>
                          )}
                          {!cudaStatus.llama_gpu_ready && (
                            <Button
                              leftIcon={<FiDownload />}
                              colorScheme="blue"
                              onClick={() => downloadCudaLibraries('llama_gpu')}
                              isLoading={cudaDownloading || cudaStatus.is_downloading}
                              size="sm"
                            >
                              Download LLaMA GPU Support
                            </Button>
                          )}
                          {(cudaStatus.whisper_gpu_ready || cudaStatus.llama_gpu_ready) && (
                            <Button
                              leftIcon={<FiTrash2 />}
                              colorScheme="red"
                              variant="outline"
                              onClick={cleanupCudaLibraries}
                              size="sm"
                            >
                              Remove GPU Libraries
                            </Button>
                          )}
                        </HStack>

                        <Text fontSize="xs" color="gray.500">
                          CUDA directory: {cudaStatus.cuda_directory}
                        </Text>
                      </>
                    )}
                  </VStack>
                </Box>
              </VStack>
            </TabPanel>

            {/* Danger Zone Tab */}
            <TabPanel>
              <Alert status="warning" mb={6}>
                <AlertIcon />
                <Box>
                  <AlertTitle>Danger Zone</AlertTitle>
                  <AlertDescription>These actions are irreversible. Make sure you know what you're doing.</AlertDescription>
                </Box>
              </Alert>

              <VStack spacing={6} align="stretch">
                <Box p={6} bg={bgColor} borderRadius="lg" borderWidth={1} borderColor="red.500">
                  <VStack spacing={4} align="stretch">
                    <Heading size="md" color="red.500">
                      <HStack>
                        <Icon as={FiTrash2} />
                        <Text>Clear Application Data</Text>
                      </HStack>
                    </Heading>

                    <Text>This will permanently delete your meeting recordings and transcripts. This action cannot be undone.</Text>

                    <VStack align="start" spacing={2}>
                      <Checkbox isChecked={wipeDb} onChange={(e) => setWipeDb(e.target.checked)}>
                        Delete database (meetings, transcripts)
                      </Checkbox>
                      <Checkbox isChecked={wipeAudio} onChange={(e) => setWipeAudio(e.target.checked)}>
                        Delete audio recordings
                      </Checkbox>
                    </VStack>

                    <Button colorScheme="red" leftIcon={<FiAlertTriangle />} onClick={onWipeOpen} isDisabled={!wipeDb && !wipeAudio}>
                      Wipe Selected Data
                    </Button>
                  </VStack>
                </Box>
              </VStack>
            </TabPanel>
          </TabPanels>
        </Tabs>
      </VStack>

      {/* Confirmation Modal */}
      <Modal isOpen={isWipeOpen} onClose={onWipeClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Confirm Data Deletion</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4} align="stretch">
              <Alert status="error">
                <AlertIcon />
                <Text>This action is permanent and cannot be undone!</Text>
              </Alert>
              <Text>You are about to delete:</Text>
              <VStack align="start" pl={4}>
                {wipeDb && <Text>• All meetings and transcripts</Text>}
                {wipeAudio && <Text>• All audio recordings</Text>}
              </VStack>
              <Text fontWeight="bold">Are you absolutely sure?</Text>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onWipeClose}>Cancel</Button>
            <Button colorScheme="red" onClick={wipeData} isLoading={wiping}>Yes, Delete Data</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Container>
  );
};

export default Settings;
