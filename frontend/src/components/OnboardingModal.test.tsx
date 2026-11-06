import '@testing-library/jest-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import OnboardingModal from './OnboardingModal';
import api from '../api/client';

vi.mock('../api/client', () => {
  return {
    default: {
      get: vi.fn(),
      put: vi.fn(),
    },
  };
});

describe('OnboardingModal Component', () => {
  const mockHierarchy = {
    Punjab: {
      Gurdaspur: ['Tehsil', 'Batala'],
      Amritsar: ['Amritsar-I', 'Amritsar-II'],
    },
    Haryana: {
      Gurugram: ['Sohna', 'Pataudi'],
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.get as any).mockImplementation((url: string) => {
      if (url === '/auth/locations/hierarchy') {
        return Promise.resolve({ data: mockHierarchy });
      }
      if (url === '/auth/me/preferences') {
        return Promise.resolve({
          data: {
            state: 'Punjab',
            district: 'Gurdaspur',
            city: 'Tehsil',
            max_reserve_price: 5000000,
            preferred_banks: ['PNB'],
          },
        });
      }
      return Promise.reject(new Error('Unknown url'));
    });
    (api.put as any).mockResolvedValue({ data: { success: true } });
  });

  it('renders nothing when isOpen is false', () => {
    const { container } = render(
      <OnboardingModal isOpen={false} onClose={vi.fn()} onComplete={vi.fn()} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('loads hierarchy and renders step 1 when open', async () => {
    render(<OnboardingModal isOpen={true} onClose={vi.fn()} onComplete={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText(/Set Your Local Research Desk/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/Target State/i)).toBeInTheDocument();
    expect(screen.getByText(/District \/ County/i)).toBeInTheDocument();
  });

  it('navigates through steps 1 -> 2 -> 3 and completes onboarding', async () => {
    const onComplete = vi.fn();
    render(<OnboardingModal isOpen={true} onClose={vi.fn()} onComplete={onComplete} />);

    // Step 1: Click "Next: Pricing & Sources →"
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Next: Pricing & Sources/i })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /Next: Pricing & Sources/i }));

    // Step 2: Criteria
    expect(screen.getByText(/Budget Range & Preferred Banks/i)).toBeInTheDocument();
    const nextSummaryBtn = screen.getByRole('button', { name: /Review Summary/i });
    fireEvent.click(nextSummaryBtn);

    // Step 3: Confirmation & Final Save
    expect(screen.getByText(/Confirm Your Research Desk/i)).toBeInTheDocument();
    const finishBtn = screen.getByRole('button', { name: /Activate Desk & Open Inventory/i });
    fireEvent.click(finishBtn);

    await waitFor(() => {
      expect(api.put).toHaveBeenCalledWith(
        '/auth/me/preferences',
        expect.objectContaining({
          state: 'Punjab',
          district: 'Gurdaspur',
          city: 'Tehsil',
          preferred_banks: ['PNB'],
        })
      );
      expect(onComplete).toHaveBeenCalled();
    });
  });
});
