package avito.innopolis.analysis.controller;

import avito.innopolis.analysis.dto.*;
import avito.innopolis.analysis.entity.AnalysisRun;
import avito.innopolis.analysis.entity.SourceAd;
import avito.innopolis.analysis.service.AnalysisService;
import jakarta.validation.Valid;
import org.apache.commons.csv.CSVRecord;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;

import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVParser;
import org.apache.commons.csv.CSVRecord;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.*;

@RestController
@RequestMapping("/api/v1")
public class AnalysisController {

    private final AnalysisService analysisService;

    private static final int ORIGINAL_MC_ID = 101;

    private static final long MAX_FILE_SIZE = 2 * 1024 * 1024;
    private static final int MAX_RECORDS = 100;

    private static final Path CSV_STORAGE =
            Path.of("data", "csv-files").toAbsolutePath().normalize();

    public AnalysisController(AnalysisService analysisService) {
        this.analysisService = analysisService;
    }

    @PostMapping("/analyses")
    public ResponseEntity<Map<String, Object>> start(@Valid @RequestBody CreateAnalysisRequest request) {
        AnalysisRun run = analysisService.start(request);
        return ResponseEntity.status(HttpStatus.ACCEPTED)
                .body(Map.of("id", run.id, "status", run.status));
    }

    @PostMapping("/source-ads")
    public ResponseEntity<AdView> create(@Valid @RequestBody CreateSourceAdRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(toAdView(analysisService.create(request)));
    }

    @GetMapping("/source-ads")
    public Map<String, List<AdView>> list() {
        return Map.of("items", analysisService.list().stream().map(this::toAdView).toList());
    }

    @GetMapping("/source-ads/{id}")
    public AdView get(@PathVariable UUID id) {
        return toAdView(analysisService.requireAd(id));
    }

    @GetMapping("/source-ads/{id}/analyses")
    public Map<String, List<RunView>> runs(@PathVariable UUID id) {
        return Map.of("items", analysisService.runs(id).stream().map(this::toRunView).toList());
    }

    @GetMapping("/analyses/{id}")
    public AnalysisResultView run(@PathVariable UUID id) {
        return analysisService.result(id);
    }

    @GetMapping("/analyses/{id}/services")
    public Map<String, List<ServiceView>> services(@PathVariable UUID id) {
        List<ServiceView> items = analysisService.services(id).stream()
                .map(service -> new ServiceView(
                        service.id,
                        service.targetMc.mcId,
                        service.serviceName,
                        service.sourceFragment,
                        service.confidence,
                        service.confirmed))
                .toList();
        return Map.of("items", items);
    }

    @GetMapping("/analyses/{id}/errors")
    public Map<String, List<ErrorView>> errors(@PathVariable UUID id) {
        List<ErrorView> items = analysisService.errors(id).stream()
                .map(error -> new ErrorView(
                        error.id, error.stage, error.errorCode, error.message))
                .toList();
        return Map.of("items", items);
    }

    private AdView toAdView(SourceAd ad) {
        return new AdView(ad.id, ad.description, ad.originalMc.mcId, ad.createdAt);
    }

    private RunView toRunView(AnalysisRun run) {
        return new RunView(
                run.id, run.sourceAd.id, run.status, run.stage,
                run.progress, run.modelVersion, run.createdAt, run.updatedAt);
    }

    @PostMapping(
            value = "/csv-files",
            consumes = MediaType.MULTIPART_FORM_DATA_VALUE
    )
    public ResponseEntity<Map<String, Object>> uploadCsv(
            @RequestParam("file") MultipartFile file
    ) {

        if (file.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "CSV-файл пуст");
        }

        String filename = file.getOriginalFilename();

        if (filename == null || !filename.toLowerCase(Locale.ROOT).endsWith(".csv")) {

            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "Требуется файл формата CSV"
            );
        }

        if (file.getSize() > MAX_FILE_SIZE) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Размер файла превышает 2 МБ");
        }

        analysisService.userId();

        try {
            byte[] bytes = file.getBytes();

            String content = new String(
                    bytes,
                    StandardCharsets.UTF_8
            );

            List<Map<String, String>> records = parseCsv(content);

            UUID fileId = UUID.randomUUID();

            Path destination = csvPath(fileId);

            Files.createDirectories(destination.getParent());

            Files.write(destination, bytes, StandardOpenOption.CREATE_NEW);

            Map<String, Object> response = new LinkedHashMap<>();

            response.put("fileId", fileId);
            response.put("filename", filename);
            response.put("recordsCount", records.size());

            return ResponseEntity
                    .status(HttpStatus.CREATED)
                    .body(response);

        } catch (IOException e) {
            throw new ResponseStatusException(
                    HttpStatus.INTERNAL_SERVER_ERROR,
                    "Не удалось сохранить CSV-файл", e);
        }
    }

    @PostMapping("/csv-files/{fileId}/analyses")
    public ResponseEntity<Map<String, Object>> analyzeCsv(
            @PathVariable UUID fileId
    ) {

        Path path = csvPath(fileId);

        if (!Files.isRegularFile(path)) {
            throw new ResponseStatusException(
                    HttpStatus.NOT_FOUND, "CSV-файл не найден");
        }

        List<Map<String, String>> records;

        try {
            String content = Files.readString(path, StandardCharsets.UTF_8);

            records = parseCsv(content);

        } catch (IOException e) {
            throw new ResponseStatusException(
                    HttpStatus.INTERNAL_SERVER_ERROR,
                    "Ошибка чтения CSV-файла", e);
        }

        List<Map<String, Object>> analyses = new ArrayList<>();

        List<Map<String, String>> errors = new ArrayList<>();

        for (Map<String, String> record : records) {
            String sourceId = record.get("id");

            String title = record.get("title");

            String description = record.get("description");

            try {
                CreateAnalysisRequest request =
                        new CreateAnalysisRequest(description, ORIGINAL_MC_ID);

                AnalysisRun run = analysisService.start(request);

                Map<String, Object> result = new LinkedHashMap<>();

                result.put("sourceId", sourceId);
                result.put("title", title);
                result.put("analysisId", run.id);
                result.put("status", run.status);

                analyses.add(result);

            } catch (RuntimeException e) {
                errors.add(Map.of(
                        "sourceId", sourceId,
                        "title", title,
                        "message", "Ошибка запуска анализа"));
            }
        }

        Map<String, Object> response = new LinkedHashMap<>();

        response.put("fileId", fileId);
        response.put("total", records.size());
        response.put("started", analyses.size());
        response.put("failed", errors.size());
        response.put("analyses", analyses);
        response.put("errors", errors);

        return ResponseEntity.status(HttpStatus.ACCEPTED).body(response);
    }

    private Path csvPath(UUID fileId) {
        UUID userId = analysisService.userId();

        return CSV_STORAGE.resolve(userId.toString()).resolve(fileId + ".csv");
    }

    private List<Map<String, String>> parseCsv(String content) {
        if (content.startsWith("\uFEFF")) {
            content = content.substring(1);
        }

        String firstLine = content.lines()
                .filter(line -> !line.isBlank())
                .findFirst()
                .orElse("");

        char delimiter = firstLine.contains(";")
                ? ';'
                : ',';

        CSVFormat format = CSVFormat.DEFAULT.builder()
                .setDelimiter(delimiter)
                .setHeader()
                .setSkipHeaderRecord(true)
                .setIgnoreHeaderCase(true)
                .setIgnoreSurroundingSpaces(true)
                .setIgnoreEmptyLines(true)
                .build();

        List<Map<String, String>> records = new ArrayList<>();

        Set<String> ids = new HashSet<>();

        try (CSVParser parser = CSVParser.parse(content, format)) {
            Map<String, Integer> headers = parser.getHeaderMap();

            int idIndex = -1;
            int titleIndex = -1;
            int descriptionIndex = -1;

            if (headers == null) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                        "В CSV отсутствуют заголовки");
            }

            for (Map.Entry<String, Integer> entry : headers.entrySet()) {
                String header = entry.getKey()
                        .trim()
                        .toLowerCase(Locale.ROOT);

                int index = entry.getValue();

                switch (header) {
                    case "id":
                        idIndex = index;
                        break;
                    case "title":
                    case "название":
                        titleIndex = index;
                        break;
                    case "description":
                    case "текст":
                        descriptionIndex = index;
                        break;
                    default:
                        break;
                }
            }

            if (headers.size() != 3 || idIndex < 0 ||
                    titleIndex < 0 || descriptionIndex < 0) {

                throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                        "CSV должен содержать три столбца: " + "id, title, description");
            }

            for (CSVRecord csvRecord : parser) {
                if (!csvRecord.isConsistent()) {
                    throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                            "Некорректная строка CSV: " + csvRecord.getRecordNumber());
                }

                String id = csvRecord.get(idIndex).trim();

                String title = csvRecord.get(titleIndex).trim();

                String description = csvRecord.get(descriptionIndex).trim();

                if (id.isBlank() || title.isBlank() || description.isBlank()) {
                    throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                            "В строке " + csvRecord.getRecordNumber() +
                                    " не заполнен id, title или description");
                }

                if (description.length() < 12 || description.length() > 10000) {
                    throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                            "Описание должно содержать " + "от 12 до 10000 символов");
                }

                if (!ids.add(id)) {
                    throw new ResponseStatusException(
                            HttpStatus.BAD_REQUEST, "Повторяющийся ID в CSV: " + id);
                }

                records.add(Map.of(
                        "id", id,
                        "title", title,
                        "description", description
                ));

                if (records.size() > MAX_RECORDS) {
                    throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                            "CSV должен содержать не более " + MAX_RECORDS + " объявлений");
                }
            }

        } catch (IOException | UncheckedIOException e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "Ошибка формата CSV-файла", e);
        }

        if (records.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "CSV не содержит объявлений");
        }

        return records;
    }
}
