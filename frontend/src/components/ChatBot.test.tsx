import '@testing-library/jest-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ChatBot from './ChatBot';
import { AnalystProvider } from '../context/AnalystContext';
import * as ragApi from '../api/rag';

// Mock api client
vi.mock('../api/client', () => {
  return {
    default: {
      defaults: {
        baseURL: 'http://localhost:8000',
      },
      get: vi.fn(),
      post: vi.fn(),
    },
  };
});

describe('ChatBot Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderChatBot = () => {
    return render(
      <MemoryRouter>
        <AnalystProvider>
          <ChatBot />
        </AnalystProvider>
      </MemoryRouter>
    );
  };

  it('renders closed toggle bubble initially', () => {
    renderChatBot();
    const launcher = screen.getByTitle(/Open Research Analyst/i);
    expect(launcher).toBeInTheDocument();
  });

  it('opens panel when toggle button is clicked', () => {
    renderChatBot();
    const launcher = screen.getByTitle(/Open Research Analyst/i);
    fireEvent.click(launcher);

    expect(screen.getByLabelText(/Foreclosure Research Analyst/i)).toBeInTheDocument();
    expect(screen.getByText(/evidence-backed valuations/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Ask about auctions/i)).toBeInTheDocument();
  });

  it('renders external and document action pills as real anchor links with target _blank', async () => {
    // Spy on askRag to return citations with action links
    vi.spyOn(ragApi, 'askRag').mockResolvedValueOnce({
      question: 'Show document notice',
      answer: 'Here is the auction notice and property details.',
      citations: [
        {
          title: 'Auction Notice PDF',
          source_id: '/documents/999/file',
          kind: 'action',
          excerpt: 'Auction notice',
          score: 1.0,
        },
        {
          title: 'PNB Bank Portal',
          source_id: 'https://pnbindia.in/sarfaesi',
          kind: 'action',
          excerpt: 'Bank portal',
          score: 1.0,
        },
        {
          title: 'View Property Record',
          source_id: '/properties/101',
          kind: 'action',
          excerpt: 'Property details',
          score: 1.0,
        },
      ],
      context_kinds: ['document'],
      property_ids: [101],
      document_ids: [999],
      chunks_used: 1,
      method: 'rag',
      mode: 'targeted',
    });

    renderChatBot();
    // Open chat
    fireEvent.click(screen.getByTitle(/Open Research Analyst/i));

    const input = screen.getByPlaceholderText(/Ask about auctions/i);
    fireEvent.change(input, { target: { value: 'Show document notice' } });

    const sendBtn = screen.getByTitle(/Send to Research Analyst/i);
    fireEvent.click(sendBtn);

    // Wait for the response to render
    await waitFor(() => {
      expect(screen.getByText(/Here is the auction notice/i)).toBeInTheDocument();
    });

    // 1. Document file link should be an <a> tag pointing to full backend baseURL + /documents/999/file
    const docLink = screen.getByRole('link', { name: /Auction Notice PDF ↗/i });
    expect(docLink).toBeInTheDocument();
    expect(docLink).toHaveAttribute('href', 'http://localhost:8000/documents/999/file');
    expect(docLink).toHaveAttribute('target', '_blank');
    expect(docLink).toHaveAttribute('rel', 'noopener noreferrer');

    // 2. External bank portal link should be an <a> tag with external target
    const extLink = screen.getByRole('link', { name: /PNB Bank Portal ↗/i });
    expect(extLink).toBeInTheDocument();
    expect(extLink).toHaveAttribute('href', 'https://pnbindia.in/sarfaesi');
    expect(extLink).toHaveAttribute('target', '_blank');

    // 3. Internal property link should be a React Router Link pointing to /properties/101
    const internalLink = screen.getByRole('link', { name: /View Property Record →/i });
    expect(internalLink).toBeInTheDocument();
    expect(internalLink).toHaveAttribute('href', '/properties/101');
    expect(internalLink).not.toHaveAttribute('target');
  });

  it('can be closed via close button', () => {
    renderChatBot();
    // Open
    fireEvent.click(screen.getByTitle(/Open Research Analyst/i));
    expect(screen.getByLabelText(/Foreclosure Research Analyst/i)).toBeInTheDocument();

    // Close
    const closeBtn = screen.getByTitle(/Close Analyst Drawer/i);
    fireEvent.click(closeBtn);

    // Should return to toggle button
    expect(screen.getByTitle(/Open Research Analyst/i)).toBeInTheDocument();
  });
});
