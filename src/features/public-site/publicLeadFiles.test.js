import { validatePublicLeadFiles, uploadPublicLeadFiles } from './publicLeadFiles';

describe('public lead files', () => {
  test('accepts up to five supported files', () => {
    const files = [
      new File(['%PDF-1.7'], 'plan.pdf', { type: 'application/pdf' }),
      new File(['photo'], 'house.jpg', { type: 'image/jpeg' }),
    ];

    expect(validatePublicLeadFiles(files)).toEqual(files);
  });

  test('rejects more than five files', () => {
    const files = Array.from({ length: 6 }, (_, index) => (
      new File(['photo'], `photo-${index}.png`, { type: 'image/png' })
    ));

    expect(() => validatePublicLeadFiles(files)).toThrow('не больше 5 файлов');
  });

  test('rejects unsupported file type', () => {
    const files = [new File(['sheet'], 'estimate.xlsx', { type: 'application/vnd.ms-excel' })];
    expect(() => validatePublicLeadFiles(files)).toThrow('PDF, JPEG, PNG или WebP');
  });

  test('uploads files and returns tokens', async () => {
    const fetchImpl = jest.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ token: 'a'.repeat(32) }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ token: 'b'.repeat(32) }) });
    const files = [
      new File(['%PDF-1.7'], 'plan.pdf', { type: 'application/pdf' }),
      new File(['photo'], 'house.jpg', { type: 'image/jpeg' }),
    ];

    await expect(uploadPublicLeadFiles(files, 'https://api.test', fetchImpl)).resolves.toEqual([
      'a'.repeat(32),
      'b'.repeat(32),
    ]);
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });
});
