import {
  Box,
  Button,
  VStack,
  Text,
  Badge,
  Divider,
  Select,
  HStack,
  Icon,
  Tooltip,
  Heading,
  Spinner,
  useColorMode,
  Image,
  Link,
} from '@chakra-ui/react';
import { FiMic, FiSquare, FiClock, FiKey } from 'react-icons/fi';
import { formatDistanceToNow } from 'date-fns';
import { useNavigate } from 'react-router-dom';
import OraiLogo from '../assets/orai_logo.svg';

interface Meeting {
  id: string;
  title: string;
  started_at: string;
  ended_at?: string;
  status: string;
  transcript_segments?: any[];
}

interface SidebarProps {
  meetingId: string | null;
  meetings: Meeting[];
  selectedMeetingId: string | null;
  onSelectMeeting: (id: string) => void;
  onStartRecording: () => void;
  onStopRecording: () => void;
  isLoadingMeetings: boolean;
  inputs: { id: string; name: string }[];
  outputs: { id: string; name: string }[];
  micId: string | undefined;
  outId: string | undefined;
  onMicChange: (id: string) => void;
  onOutChange: (id: string) => void;
}

export default function Sidebar({
  meetingId,
  meetings,
  selectedMeetingId,
  onSelectMeeting,
  onStartRecording,
  onStopRecording,
  isLoadingMeetings,
  inputs,
  outputs,
  micId,
  outId,
  onMicChange,
  onOutChange,
}: SidebarProps) {
  const { colorMode } = useColorMode();
  const navigate = useNavigate();

  return (
    <Box
      w="320px"
      bg={colorMode === 'dark' ? 'gray.900' : 'gray.50'}
      borderRight="1px"
      borderRightColor={colorMode === 'dark' ? 'gray.700' : 'gray.200'}
      display="flex"
      flexDirection="column"
    >
      {/* Recording Controls */}
      <Box p={4} borderBottom="1px" borderBottomColor={colorMode === 'dark' ? 'gray.700' : 'gray.200'}>
        <VStack spacing={3} align="stretch">
          <Select
            size="sm"
            placeholder="Select microphone"
            value={micId}
            onChange={(e) => onMicChange(e.target.value)}
            isDisabled={!!meetingId}
          >
            {inputs.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </Select>
          <Select
            size="sm"
            placeholder="Select output device"
            value={outId}
            onChange={(e) => onOutChange(e.target.value)}
            isDisabled={!!meetingId}
          >
            {outputs.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </Select>

          {meetingId ? (
            <Button
              colorScheme="red"
              leftIcon={<Icon as={FiSquare} />}
              onClick={onStopRecording}
              size="md"
              w="full"
            >
              Stop Recording
            </Button>
          ) : (
            <Button
              colorScheme="green"
              leftIcon={<Icon as={FiMic} />}
              onClick={onStartRecording}
              isDisabled={!micId || !outId}
              size="md"
              w="full"
            >
              Start Recording
            </Button>
          )}

          {meetingId && (
            <Badge colorScheme="green" fontSize="sm" p={2} textAlign="center">
              Recording Meeting #{meetingId}
            </Badge>
          )}
        </VStack>
      </Box>

      {/* Meetings List */}
      <Box flex="1" overflowY="auto">
        <Box p={4}>
          <Heading size="sm" mb={3} color={colorMode === 'dark' ? 'gray.300' : 'gray.700'}>
            Meetings
          </Heading>

          {isLoadingMeetings ? (
            <Box textAlign="center" py={4}>
              <Spinner size="sm" />
            </Box>
          ) : meetings && meetings.length > 0 ? (
            <VStack spacing={2} align="stretch">
              {meetings.map((meeting) => (
                <Box
                  key={meeting.id}
                  p={3}
                  bg={
                    selectedMeetingId === meeting.id
                      ? colorMode === 'dark'
                        ? 'gray.700'
                        : 'white'
                      : 'transparent'
                  }
                  borderRadius="md"
                  cursor="pointer"
                  onClick={() => onSelectMeeting(meeting.id)}
                  _hover={{
                    bg: colorMode === 'dark' ? 'gray.800' : 'white',
                  }}
                  transition="background 0.2s"
                  boxShadow={selectedMeetingId === meeting.id ? 'sm' : 'none'}
                >
                  <VStack align="stretch" spacing={1}>
                    <HStack justify="space-between">
                      <Text
                        fontWeight="semibold"
                        fontSize="sm"
                        noOfLines={1}
                      >
                        {meeting.title || `Meeting #${meeting.id}`}
                      </Text>
                      {meeting.status === 'recording' && (
                        <Badge colorScheme="green" fontSize="xs">
                          Live
                        </Badge>
                      )}
                    </HStack>

                    <HStack spacing={3} fontSize="xs" color="gray.500">
                      <HStack spacing={1}>
                        <Icon as={FiClock} />
                        <Text>
                          {formatDistanceToNow(new Date(meeting.started_at), { addSuffix: true })}
                        </Text>
                      </HStack>

                      
                    </HStack>

                    {meeting.ended_at && (
                      <Text fontSize="xs" color="gray.500">
                        Duration: {getDuration(meeting.started_at, meeting.ended_at)}
                      </Text>
                    )}
                  </VStack>
                </Box>
              ))}
            </VStack>
          ) : (
            <Text color="gray.500" fontSize="sm" textAlign="center">
              No meetings yet. Start recording to create one.
            </Text>
          )}
        </Box>
      </Box>

      {/* Footer */}
      <Box p={4} borderTop="1px" borderTopColor={colorMode === 'dark' ? 'gray.700' : 'gray.200'}>
        <HStack justify="space-between" align="center">
          <Link href="https://orai-solutions.de/" isExternal>
            <Image src={OraiLogo} alt="ORAI" h="16px" />
          </Link>
        </HStack>
      </Box>
    </Box>
  );
}

function getDuration(startTime: string, endTime: string): string {
  const start = new Date(startTime);
  const end = new Date(endTime);
  const diff = end.getTime() - start.getTime();
  const hours = Math.floor(diff / 3600000);
  const minutes = Math.floor((diff % 3600000) / 60000);
  const seconds = Math.floor((diff % 60000) / 1000);

  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  } else if (minutes > 0) {
    return `${minutes}m ${seconds}s`;
  } else {
    return `${seconds}s`;
  }
}
