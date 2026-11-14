package avito.innopolis.analysis.controller;

import avito.innopolis.analysis.dto.*;
import avito.innopolis.analysis.entity.AnalysisRun;
import avito.innopolis.analysis.entity.SourceAd;
import avito.innopolis.analysis.service.AnalysisService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1")
public class AnalysisController {

    private final AnalysisService analysisService;

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
}
