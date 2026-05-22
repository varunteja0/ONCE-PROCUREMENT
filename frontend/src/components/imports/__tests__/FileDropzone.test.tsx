// --- L3.7 imports ---
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { FileDropzone } from '@/components/imports/FileDropzone';

describe('FileDropzone', () => {
  function fileOf(name: string, content = 'a,b\n1,2', type = 'text/csv'): File {
    return new File([content], name, { type });
  }

  it('accepts a CSV via the hidden input and calls onFileSelected', () => {
    const onFile = vi.fn();
    render(<FileDropzone onFileSelected={onFile} />);
    const input = document.querySelector('input[type=file]') as HTMLInputElement;
    const f = fileOf('suppliers.csv');
    fireEvent.change(input, { target: { files: [f] } });
    expect(onFile).toHaveBeenCalledWith(f);
  });

  it('rejects an unsupported extension with an inline error', () => {
    const onFile = vi.fn();
    render(<FileDropzone onFileSelected={onFile} />);
    const input = document.querySelector('input[type=file]') as HTMLInputElement;
    fireEvent.change(input, {
      target: { files: [fileOf('bad.exe', 'x', 'application/octet-stream')] },
    });
    expect(onFile).not.toHaveBeenCalled();
    expect(screen.getByRole('alert').textContent).toMatch(/Unsupported/i);
  });

  it('rejects files larger than maxBytes', () => {
    const onFile = vi.fn();
    render(<FileDropzone onFileSelected={onFile} maxBytes={4} />);
    const input = document.querySelector('input[type=file]') as HTMLInputElement;
    // 10 bytes > 4
    fireEvent.change(input, { target: { files: [fileOf('big.csv', '0123456789')] } });
    expect(onFile).not.toHaveBeenCalled();
    expect(screen.getByRole('alert').textContent).toMatch(/too large/i);
  });

  it('handles dropped files', () => {
    const onFile = vi.fn();
    render(<FileDropzone onFileSelected={onFile} />);
    const zone = screen.getByRole('button', { name: /Upload CSV or XLSX file/i });
    const f = fileOf('drop.csv');
    fireEvent.drop(zone, { dataTransfer: { files: [f] } });
    expect(onFile).toHaveBeenCalledWith(f);
  });

  it('opens the file picker on Enter key', () => {
    const onFile = vi.fn();
    render(<FileDropzone onFileSelected={onFile} />);
    const input = document.querySelector('input[type=file]') as HTMLInputElement;
    const click = vi.spyOn(input, 'click');
    const zone = screen.getByRole('button', { name: /Upload CSV or XLSX file/i });
    fireEvent.keyDown(zone, { key: 'Enter' });
    expect(click).toHaveBeenCalled();
  });
});
// --- /L3.7 imports ---
