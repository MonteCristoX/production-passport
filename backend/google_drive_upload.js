const fs = require('node:fs');
const { ReplitConnectors } = require('@replit/connectors-sdk');

const DOCX_MIME =
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document';

async function uploadDocx(filePath, fileName) {
  const fileBytes = fs.readFileSync(filePath);
  const boundary = `production-passport-${Date.now().toString(16)}`;
  const metadata = JSON.stringify({
    name: fileName,
    mimeType: DOCX_MIME,
  });

  const body = Buffer.concat([
    Buffer.from(
      `--${boundary}\r\n` +
        'Content-Type: application/json; charset=UTF-8\r\n\r\n' +
        `${metadata}\r\n` +
        `--${boundary}\r\n` +
        `Content-Type: ${DOCX_MIME}\r\n\r\n`,
      'utf8',
    ),
    fileBytes,
    Buffer.from(`\r\n--${boundary}--\r\n`, 'utf8'),
  ]);

  const connectors = new ReplitConnectors();
  const response = await connectors.proxy(
    'google-drive',
    '/upload/drive/v3/files?uploadType=multipart&fields=id,name,mimeType,webViewLink',
    {
      method: 'POST',
      headers: {
        'Content-Type': `multipart/related; boundary=${boundary}`,
        'Content-Length': String(body.length),
      },
      body,
    },
  );

  const responseText = await response.text();
  let responseBody;
  try {
    responseBody = JSON.parse(responseText);
  } catch {
    responseBody = { message: responseText || response.statusText };
  }

  if (!response.ok) {
    const message =
      responseBody.error?.message ||
      responseBody.message ||
      `Google Drive returned HTTP ${response.status}`;
    throw new Error(message);
  }

  return responseBody;
}

async function main() {
  const [, , filePath, fileName] = process.argv;
  if (!filePath || !fileName) {
    throw new Error('Usage: node google_drive_upload.js <file-path> <file-name>');
  }

  const uploaded = await uploadDocx(filePath, fileName);
  process.stdout.write(
    JSON.stringify({
      success: true,
      id: uploaded.id,
      name: uploaded.name,
      webViewLink: uploaded.webViewLink,
    }),
  );
}

main().catch((error) => {
  process.stderr.write(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});