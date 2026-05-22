// --- L3.8 pdf extraction ---
/**
 * Drop-in wrapper that turns any existing "upload + show row" page into
 * an extraction-aware page **without editing the host component**.
 *
 * Usage:
 * ```tsx
 * <ExtractionAwareUpload
 *   documentType="coi"
 *   documentId={coi.id}
 * >
 *   <ExistingCoiUploadCard />
 * </ExtractionAwareUpload>
 * ```
 *
 * Behaviour:
 *   * On mount with a `documentId`, the wrapper does NOT auto-enqueue
 *     (we don't know if the host already triggered one). The user
 *     clicks "Extract metadata" to enqueue.
 *   * Once an extraction is enqueued, the wrapper polls until it
 *     leaves `pending` then renders the editable
 *     :func:`ExtractedFieldsPanel`.
 *   * Accept / Reject events bubble up via the `onAccepted` /
 *     `onRejected` callbacks; the host page typically uses these to
 *     refresh its own data.
 */

import { useState, type PropsWithChildren } from 'react';

import {
  useAcceptExtraction,
  useEnqueueExtraction,
  useExtraction,
  useRejectExtraction,
} from '@/hooks/useExtraction';
import type { ExtractionSourceType } from '@/services/extractionsApi';

import { ExtractedFieldsPanel } from './ExtractedFieldsPanel';

export interface ExtractionAwareUploadProps {
  documentType: ExtractionSourceType;
  documentId: string;
  /** Optional pre-existing extraction id (skip the enqueue step). */
  initialExtractionId?: string;
  onAccepted?: (overrides: Record<string, unknown>) => void;
  onRejected?: (reason: string) => void;
}

export function ExtractionAwareUpload({
  documentType,
  documentId,
  initialExtractionId,
  onAccepted,
  onRejected,
  children,
}: PropsWithChildren<ExtractionAwareUploadProps>): JSX.Element {
  const [extractionId, setExtractionId] = useState<string | undefined>(
    initialExtractionId,
  );

  const enqueue = useEnqueueExtraction();
  const accept = useAcceptExtraction();
  const reject = useRejectExtraction();
  const extractionQuery = useExtraction(extractionId, { pollWhilePending: true });

  async function handleEnqueue() {
    const row = await enqueue.mutateAsync({
      document_type: documentType,
      document_id: documentId,
    });
    setExtractionId(row.id);
  }

  return (
    <div className="space-y-4">
      {children}

      {!extractionId && (
        <button
          type="button"
          data-testid="enqueue-extraction"
          onClick={handleEnqueue}
          disabled={enqueue.isPending}
          className="rounded bg-blue-600 px-3 py-1 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {enqueue.isPending ? 'Enqueueing…' : 'Extract metadata'}
        </button>
      )}

      {extractionId && extractionQuery.data && extractionQuery.data.status === 'pending' && (
        <p data-testid="extraction-pending" className="text-sm text-gray-500">
          Running extractor… (polling)
        </p>
      )}

      {extractionId && extractionQuery.data && extractionQuery.data.status !== 'pending' && (
        <ExtractedFieldsPanel
          extraction={extractionQuery.data}
          readOnly={['accepted', 'rejected'].includes(extractionQuery.data.status)}
          onAccept={
            ['accepted', 'rejected'].includes(extractionQuery.data.status)
              ? undefined
              : async (overrides) => {
                  await accept.mutateAsync({ id: extractionId, fields: overrides });
                  onAccepted?.(overrides);
                }
          }
          onReject={
            ['accepted', 'rejected'].includes(extractionQuery.data.status)
              ? undefined
              : async (reason) => {
                  await reject.mutateAsync({ id: extractionId, reason });
                  onRejected?.(reason);
                }
          }
        />
      )}
    </div>
  );
}

export default ExtractionAwareUpload;
// --- /L3.8 pdf extraction ---
