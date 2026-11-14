package avito.innopolis.draft.controller;

import avito.innopolis.draft.dto.DraftItem;
import avito.innopolis.draft.dto.DraftPatch;
import avito.innopolis.draft.dto.DraftStatePatch;
import avito.innopolis.draft.dto.DraftView;
import avito.innopolis.draft.entity.Draft;
import avito.innopolis.draft.service.DraftService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1")
public class DraftController {

    private final DraftService draftService;

    public DraftController(DraftService draftService) {
        this.draftService = draftService;
    }

    @GetMapping("/analyses/{id}/drafts")
    public Map<String, List<DraftView>> list(@PathVariable UUID id) {
        return Map.of("items", draftService.forRun(id).stream().map(this::toView).toList());
    }

    @GetMapping("/drafts")
    public Map<String, List<DraftView>> listAll(@RequestParam(required = false) String state) {
        return Map.of("items", draftService.list(state).stream().map(this::toView).toList());
    }

    @GetMapping("/analyses/{id}/result")
    public Map<String, List<DraftItem>> result(@PathVariable UUID id) {
        List<DraftItem> drafts = draftService.forRun(id).stream()
                .map(draft -> new DraftItem(draft.targetMc.mcId, draft.title, draft.body))
                .toList();
        return Map.of("drafts", drafts);
    }

    @GetMapping("/drafts/{id}")
    public DraftView get(@PathVariable UUID id) {
        return toView(draftService.get(id));
    }

    @PatchMapping("/drafts/{id}")
    public DraftView patch(@PathVariable UUID id, @Valid @RequestBody DraftPatch patch) {
        return toView(draftService.update(id, patch));
    }

    @PatchMapping("/drafts/{id}/state")
    public DraftView changeState(@PathVariable UUID id, @Valid @RequestBody DraftStatePatch patch) {
        return toView(draftService.changeState(id, patch));
    }

    @DeleteMapping("/drafts/{id}")
    public ResponseEntity<Void> delete(@PathVariable UUID id) {
        draftService.delete(id);
        return ResponseEntity.noContent().build();
    }

    private DraftView toView(Draft draft) {
        return new DraftView(
                draft.id, draft.analysis.id, draft.analysis.sourceAd.id, draft.targetMc.mcId,
                draft.title, draft.body, draft.status, draft.collectionState, draft.createdAt, draft.updatedAt);
    }
}
