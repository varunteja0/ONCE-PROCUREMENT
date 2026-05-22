// --- L3.9 inbound ---
import { Paperclip } from 'lucide-react';
import type { InboundAttachment } from '@/services/inboundApi';

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(2)} MB`;
}

export function AttachmentList({
  attachments,
}: {
  attachments: InboundAttachment[];
}): JSX.Element {
  if (attachments.length === 0) {
    return (
      <p className="text-sm text-gray-500 dark:text-gray-400">No attachments.</p>
    );
  }
  return (
    <ul className="divide-y divide-gray-200 rounded-md border border-gray-200 dark:divide-gray-700 dark:border-gray-700">
      {attachments.map((att) => (
        <li
          key={att.id}
          className="flex items-center justify-between gap-3 px-3 py-2 text-sm"
        >
          <div className="flex min-w-0 items-center gap-2">
            <Paperclip className="h-4 w-4 flex-shrink-0 text-gray-400" />
            <div className="min-w-0">
              <div className="truncate font-medium" title={att.filename}>
                {att.filename}
              </div>
              <div className="truncate text-xs text-gray-500 dark:text-gray-400">
                {att.content_type ?? 'application/octet-stream'} ·{' '}
                {formatBytes(att.size_bytes)} · sha256:{att.sha256.slice(0, 12)}…
              </div>
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}

export default AttachmentList;
