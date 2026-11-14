package avito.innopolis.draft.service;

import avito.innopolis.analysis.service.AnalysisService;
import avito.innopolis.common.exception.ApiException;
import avito.innopolis.draft.dto.DraftPatch;
import avito.innopolis.draft.entity.Draft;
import avito.innopolis.draft.repository.DraftRepository;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

@Service
@Transactional(readOnly = true)
public class DraftService {

    private final DraftRepository draftRepository;
    private final AnalysisService analysisService;

    public DraftService(DraftRepository draftRepository, AnalysisService analysisService) {
        this.draftRepository = draftRepository;
        this.analysisService = analysisService;
    }

    public List<Draft> forRun(UUID analysisId) {
        analysisService.requireRun(analysisId);
        return draftRepository.findByAnalysis_IdOrderByCreatedAtAsc(analysisId);
    }

    public Draft get(UUID draftId) {
        return draftRepository.findByIdAndAnalysis_SourceAd_User_Id(
                        draftId, analysisService.userId())
                .orElseThrow(() -> new ApiException(
                        HttpStatus.NOT_FOUND, "DRAFT_NOT_FOUND", "Черновик не найден"));
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
