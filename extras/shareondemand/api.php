<?php
declare(strict_types=1);

namespace Photobooth;
use RuntimeException;
use function strlen, count, intval; // use global functions

const API_KEY = "changedefault!";   // <-- user changes this

final class ShareService
{
    private const array ALLOWED_TYPES = [
        'image/png' => 'png',
        'image/jpeg' => 'jpg',
        'image/jpg' => 'jpg',
        'image/avif' => 'avif',
        'image/webp' => 'webp',
        'image/gif' => 'gif',
        'video/mp4' => 'mp4',
    ];

    public function __construct(
        private string $apiKey,
        private string $workDir,
        private string $jobDir,
        private int $maxSize = 25 * 2 ** 20, //25 Mb
        private int $timeout = 15   // s
    ) {
        if (!is_dir($workDir))
            if (!mkdir($workDir, 0775, true))
                throw new RuntimeException("The workDir $workDir is not writeable.");
        if (!is_dir($jobDir))
            if (!mkdir($jobDir, 0775, true))
                throw new RuntimeException("The jobDir $jobDir is not writeable.");


        ini_set('display_startup_errors', 0);
        ini_set('display_errors', 0);
        ini_set('log_errors', 1);
        ini_set('error_log', __DIR__ . "/php-error.log");
        ini_set('pcre.jit', 0);

        // prevent nginx from additional buffering because the long running job would fail then
        // nginx has additional buffer to php, the php buffer is flushed, but nginx not
        header('X-Accel-Buffering: no');
        ob_implicit_flush(true);
    }

    private function validateApiKey(string $key): void
    {
        if (strlen($this->apiKey) < 8) {
            throw new RuntimeException('The API key is empty or too short! Configure the key in the php script and set it in the photobooth-app config.');
        }
        if ($this->apiKey == "changedefault!") {
            throw new RuntimeException('The API key is the default value in the PHP script! Change the API key in the PHP script and the photobooth-app config.');
        }
        if ($key !== $this->apiKey) {
            throw new RuntimeException("Invalid API key!");
        }
    }

    private function clearJob(string $id): void
    {
        // just keep uploaded status
        foreach (["pending", "assigned", "failed"] as $s) {
            @unlink($this->jobFile($id, $s));
        }
    }


    private function jobFile(string $id, string $status): string
    {
        return "$this->jobDir/$id.$status";
    }

    private function setStatus(string $id, string $status): void
    {
        $this->clearJob($id);
        file_put_contents($this->jobFile($id, $status), "1");
    }

    private function hasStatus(string $id, string $status): bool
    {
        return file_exists($this->jobFile($id, $status));
    }

    private function hasAnyStatus(string $id): bool
    {
        return count(glob($this->jobFile($id, "*"))) > 0;
    }



    public function uploadQueue(): void
    {
        $this->validateApiKey($_POST['apikey'] ?? '');

        $loopTime = 0.5;
        $loopTime_us = intval($loopTime * 1_000_000);
        $maxTime = 240;
        $elapsed = 0;


        while ($elapsed <= $maxTime) {
            $pending = glob("$this->jobDir/*.pending");

            if (!empty($pending)) {
                $file = basename($pending[0]);
                $id = explode(".", $file)[0];

                $this->setStatus($id, "assigned");

                echo json_encode(["id" => $id]) . "\n";
            } else {
                echo json_encode(["ping" => time()]) . "\n";

            }

            if (ob_get_level() > 0)
                ob_flush(); # flush internal buffer (needed for php builtin webserver during testing)
            flush();   # flush output buffer

            usleep($loopTime_us);
            $elapsed += $loopTime;
        }
    }

    public function upload(): void
    {
        $this->validateApiKey($_POST['apikey'] ?? '');

        $id = $_POST['id'] ?? null;

        if (!$id) {
            throw new RuntimeException("Missing id");
        }

        if (!$this->hasStatus($id, "assigned")) {
            throw new RuntimeException("File not assigned to a client to upload, id=$id");
        }

        if (!isset($_FILES['upload_file'])) {
            $this->setStatus($id, "failed");
            throw new RuntimeException("No file uploaded");
        }

        $tmp = $_FILES['upload_file']['tmp_name'];
        if (!$tmp || filesize($tmp) === 0) {
            $this->setStatus($id, "failed");
            throw new RuntimeException("Empty file");
        }
        if (filesize($tmp) > $this->maxSize) {
            $this->setStatus($id, "failed");
            throw new RuntimeException("File too large");
        }

        $mime = mime_content_type($tmp);
        if (!isset(self::ALLOWED_TYPES[$mime])) {
            $this->setStatus($id, "failed");
            throw new RuntimeException("File type not allowed");
        }

        $ext = self::ALLOWED_TYPES[$mime];
        $filename = "$id.$ext";
        $dest = "$this->workDir/$filename";

        if (!move_uploaded_file($tmp, $dest)) {
            $this->setStatus($id, "failed");
            throw new RuntimeException("Failed to store file");
        }

        $this->setStatus($id, "uploaded");

        echo json_encode([
            "detail" => "ok",
            "type" => "message"
        ]);
    }

    public function download(): void
    {
        $id = $_GET['id'] ?? null;
        if (!$id) {
            throw new RuntimeException("Missing id");
        }

        if (!$this->hasAnyStatus($id)) {
            $this->setStatus($id, "pending");
        }

        $wait = 0;
        while ($wait < $this->timeout) {
            // first to check if the file is already avail on server:
            if ($this->hasStatus($id, "uploaded")) {
                $file = glob("$this->workDir/$id.*")[0] ?? null;
                if (!$file || !file_exists($file)) {
                    throw new RuntimeException("File missing");
                }

                header("Content-Type: " . mime_content_type($file));
                readfile($file);
                return;
            }

            //second check is to see if the upload failed, inform about it but delete the job data so it could be uploaded again.
            if ($this->hasStatus($id, "failed")) {
                $this->clearJob($id);
                throw new RuntimeException("Upload failed");
            }

            usleep(500_000);
            $wait += 0.5;
            continue;


        }

        $this->clearJob($id);
        throw new RuntimeException("Timeout waiting for photobooth");
    }

    public function version(): void
    {
        echo json_encode([
            "detail" => "1",
            "type" => "version"
        ]);
    }
    public function cleanupOldFiles(int $maxAgeSeconds = 600): void
    {
        $now = time();

        // Cleanup job files
        foreach (glob("$this->jobDir/*.*") as $file) {
            if (is_file($file)) {
                $age = $now - filemtime($file);
                if ($age > $maxAgeSeconds) {
                    @unlink($file);
                }
            }
        }

        // Cleanup uploaded media files
        foreach (glob("$this->workDir/*.*") as $file) {
            if (is_file($file)) {
                $age = $now - filemtime($file);
                if ($age > $maxAgeSeconds) {
                    @unlink($file);
                }
            }
        }
    }
}

$service = new ShareService(
    apiKey: API_KEY,
    workDir: __DIR__ . "/uploads",
    jobDir: __DIR__ . "/jobs"
);

try {
    $service->cleanupOldFiles();   // auto-cleanup

    $action = $_REQUEST['action'] ?? null;

    switch ($action) {
        case "upload_queue":
            $service->uploadQueue();
            break;
        case "upload":
            $service->upload();
            break;
        case "download":
            $service->download();
            break;
        case "version":
            $service->version();
            break;
        default:
            http_response_code(400); // bad request
            echo json_encode([
                "detail" => "unknown action",
                "type" => "error"
            ]);
    }
} catch (RuntimeException $e) {
    error_log("RuntimeException: " . $e->getMessage());

    // JSON is safest for browser + photobooth
    http_response_code(500);
    echo json_encode([
        "detail" => $e->getMessage(),
        "type" => "error"
    ]);


}
