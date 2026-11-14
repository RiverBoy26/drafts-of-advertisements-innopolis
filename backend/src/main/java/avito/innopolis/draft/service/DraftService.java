package avito.innopolis.draft.service;

import avito.innopolis.analysis.service.AnalysisService;
import avito.innopolis.common.exception.ApiException;
import avito.innopolis.draft.dto.DraftPatch;
import avito.innopolis.draft.dto.DraftStatePatch;
import avito.innopolis.draft.entity.Draft;
import avito.innopolis.draft.repository.DraftEvidenceRepository;
import avito.innopolis.draft.repository.DraftRepository;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Set;
import java.util.UUID;

@Service
@Transactional(readOnly = true)
public class DraftService {

    private static final Set<String> COLLECTION_STATES = Set.of("suggested", "draft", "ready");

    private final DraftRepository draftRepository;
    private final DraftEvidenceRepository evidenceRepository;
    private final AnalysisService analysisService;

    public DraftService(DraftRepository draftRepository, DraftEvidenceRepository evidenceRepository, AnalysisService analysisService) {
        this.draftRepository = draftRepository;
        this.evidenceRepository = evidenceRepository;
        this.analysisService = analysisService;
    }

    public List<Draft> forRun(UUID analysisId) {
        analysisService.requireRun(analysisId);
        return draftRepository.findByAnalysis_IdOrderByCreatedAtAsc(analysisId);
    }

    public List<Draft> list(String state) {
        if (state == null) {
            return draftRepository.findByAnalysis_SourceAd_User_IdOrderByCreatedAtDesc(analysisService.userId());
        }
        requireState(state);
        return draftRepository.findByAnalysis_SourceAd_User_IdAndCollectionStateOrderByCreatedAtDesc(analysisService.userId(), state);
    }

    public Draft get(UUID draftId) {
        return draftRepository.findByIdAndAnalysis_SourceAd_User_Id(
                        draftId, analysisService.userId())
                .orElseThrow(() -> new ApiException(
                        HttpStatus.NOT_FOUND, "DRAFT_NOT_FOUND", "Черновик не найден"));
    }

    @Transactional
    public Draft changeState(UUID draftId, DraftStatePatch patch) {
        requireState(patch.state());
        Draft draft = get(draftId);
        if ("ready".equals(patch.state()) &&
                (draft.title == null || draft.title.isBlank() || draft.body == null || draft.body.isBlank())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "INCOMPLETE_DRAFT", "Для готового объявления заполните заголовок и текст");
        }
        draft.collectionState = patch.state();
        return draftRepository.saveAndFlush(draft);
    }

    @Transactional
    public void delete(UUID draftId) {
        Draft draft = get(draftId);
        evidenceRepository.deleteByDraft_Id(draftId);
        draftRepository.delete(draft);
    }

    private void requireState(String state) {
        if (!COLLECTION_STATES.contains(state)) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "INVALID_DRAFT_STATE", "Допустимые состояния: suggested, draft, ready");
        }
    }

    @Transactional
    public Draft update(UUID draftId, DraftPatch patch) {
        if (patch.title() == null && patch.text() == null) {
            throw new ApiException(
                    HttpStatus.BAD_REQUEST, "EMPTY_PATCH", "Укажите title и/или text");
        }

        Draft draft = get(draftId);
        if (patch.title() != null) {
            if (patch.title().isBlank()) {
                throw new ApiException(
                        HttpStatus.BAD_REQUEST, "INVALID_TITLE", "Заголовок не может быть пустым");
            }
            draft.title = patch.title().strip();
        }
        if (patch.text() != null) {
            if (patch.text().isBlank()) {
                throw new ApiException(
                        HttpStatus.BAD_REQUEST, "INVALID_TEXT", "Текст не может быть пустым");
            }
            draft.body = patch.text().strip();
        }

        draft.status = "edited";
        return draftRepository.saveAndFlush(draft);
    }
}
