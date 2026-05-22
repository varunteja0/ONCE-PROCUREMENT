// --- L3.9 inbound ---
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AttachmentList } from '../AttachmentList';
import type { InboundAttachment } from '@/services/inboundApi';

const sample: InboundAttachment[] = [
  {
    id: 'a1',
    filename: 'quote.pdf',
    content_type: 'application/pdf',
    size_bytes: 2048,
    sha256: 'a'.repeat(64),
    storage_url: 'file:///tmp/a1',
    scanned_at: null,
  },
];

describe('AttachmentList', () => {
  it('renders filename and size', () => {
    render(<AttachmentList attachments={sample} />);
    expect(screen.getByText('quote.pdf')).toBeInTheDocument();
    expect(screen.getByText(/2\.0 KB/)).toBeInTheDocument();
  });

  it('shows empty state when no attachments', () => {
    render(<AttachmentList attachments={[]} />);
    expect(screen.getByText(/No attachments/)).toBeInTheDocument();
  });
});
