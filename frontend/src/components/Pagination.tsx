import { Button } from "./Button";

export const PAGE_SIZE = 50;
export function Pagination({ page, total, onChange }: { page: number; total: number; onChange: (page: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  return <nav className="ledger-pagination" aria-label="Ledger pages">
    <Button disabled={page === 0} onClick={() => onChange(page - 1)}>Previous page</Button>
    <span role="status">{total ? `${page * PAGE_SIZE + 1}–${Math.min(total, (page + 1) * PAGE_SIZE)} of ${total}` : "0 documents"}<span className="pagination-page"> · Page {page + 1} of {pages}</span></span>
    <Button disabled={page + 1 >= pages} onClick={() => onChange(page + 1)}>Next page</Button>
  </nav>;
}
