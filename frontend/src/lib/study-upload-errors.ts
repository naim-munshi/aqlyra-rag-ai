/** Stable, non-secret upload failure messages for the Study Abroad workflow. */
export function studyUploadErrorMessage(status: number): string {
  switch (status) {
    case 401:
      return "Your session expired. Sign in again before uploading private documents.";
    case 413:
      return "The upload limit on this path is 3 MiB. Choose a smaller file.";
    case 415:
      return "Unsupported file format. Use PDF, Word, Excel, PowerPoint or plain text.";
    case 429:
      return "Too many upload attempts. Please try again later.";
    case 503:
      return "Private document storage is temporarily unavailable. Your new file was not saved.";
    default:
      return "Document upload failed. Please check the file and try again.";
  }
}
