import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'jest-axe';
import { Modal } from '@/components/ui/Modal';

describe('Modal', () => {
  it('does not render when closed', () => {
    render(<Modal open={false} onClose={() => {}} title="Hi">body</Modal>);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('renders dialog with title when open', () => {
    render(<Modal open onClose={() => {}} title="Hi">body</Modal>);
    expect(screen.getByRole('dialog', { name: 'Hi' })).toBeInTheDocument();
  });

  it('closes on Escape key', async () => {
    const onClose = vi.fn();
    render(<Modal open onClose={onClose} title="Hi">body</Modal>);
    await userEvent.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalled();
  });

  it('closes via close button', async () => {
    const onClose = vi.fn();
    render(<Modal open onClose={onClose} title="Hi">body</Modal>);
    await userEvent.click(screen.getByRole('button', { name: 'Close dialog' }));
    expect(onClose).toHaveBeenCalled();
  });

  it('has no a11y violations', async () => {
    const { container } = render(
      <Modal open onClose={() => {}} title="Hi" description="d">body</Modal>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
