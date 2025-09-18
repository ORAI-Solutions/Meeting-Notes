import { ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  Box,
  Heading,
  Link as ChakraLink,
  List as ChakraList,
  ListItem as ChakraListItem,
  Text,
  useColorMode,
} from '@chakra-ui/react';

type MarkdownProps = {
  children: string | ReactNode;
};

export default function Markdown({ children }: MarkdownProps) {
  const { colorMode } = useColorMode();
  return (
    <Box
      sx={{
        'ul, ol': {
          pl: 5,
          my: 2,
        },
        li: {
          mb: 1,
        },
        p: {
          my: 2,
        },
        a: {
          color: 'blue.500',
          textDecoration: 'underline',
        },
        code: {
          px: 1,
          py: 0.5,
          rounded: 'sm',
          bg: colorMode === 'dark' ? 'gray.700' : 'gray.100',
          fontSize: '0.95em',
        },
      }}
    >
      <ReactMarkdown
        components={{
          h1: ({ node, ...props }) => (
            <Heading size="md" my={2} {...props} />
          ),
          h2: ({ node, ...props }) => (
            <Heading size="sm" my={2} {...props} />
          ),
          h3: ({ node, ...props }) => (
            <Heading size="xs" my={2} {...props} />
          ),
          p: ({ node, ...props }) => <Text {...props} />,
          a: ({ node, href, ...props }) => (
            <ChakraLink href={href} isExternal {...props} />
          ),
          ul: ({ node, ...props }) => (
            <ChakraList styleType="disc" spacing={1} {...props} />
          ),
          ol: ({ node, ...props }) => (
            <ChakraList as="ol" styleType="decimal" spacing={1} {...props} />
          ),
          li: ({ node, children, ...props }) => (
            <ChakraListItem {...props}>{children}</ChakraListItem>
          ),
        }}
      >
        {typeof children === 'string' ? children : String(children)}
      </ReactMarkdown>
    </Box>
  );
}


