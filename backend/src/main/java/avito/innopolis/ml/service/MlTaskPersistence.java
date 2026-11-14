package avito.innopolis.ml.service;

import avito.innopolis.analysis.entity.AnalysisRun;
import avito.innopolis.analysis.entity.ProcessingError;
import avito.innopolis.analysis.repository.AnalysisRunRepository;
import avito.innopolis.analysis.repository.ProcessingErrorRepository;
import avito.innopolis.catalog.repository.MicrocategoryRepository;
import avito.innopolis.draft.entity.Draft;
import avito.innopolis.draft.repository.DraftRepository;
import avito.innopolis.ml.dto.MlDraft;
import avito.innopolis.ml.dto.MlRequest;
import avito.innopolis.ml.dto.MlResponse;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;
import java.util.UUID;

@Service
public class MlTaskPersistence {

    private final AnalysisRunRepository runs;
    private final ProcessingErrorRepository errors;
    private final DraftRepository drafts;
    private final MicrocategoryRepository microcategories;
    private final MlResultValidator validator;

    public MlTaskPersistence(
            AnalysisRunRepository runs,
            ProcessingErrorRepository errors,
            DraftRepository drafts,
            MicrocategoryRepository microcategories,
            MlResultValidator validator
    ) {
        this.runs = runs;
        this.errors = errors;
        this.drafts = drafts;
        this.microcategories = microcategories;
        this.validator = validator;
    }

    @Transactional
    public MlRequest begin(UUID id) {

        AnalysisRun run = runs.findById(id).orElseThrow();

        if (!"queued".equals(run.status)) {
            throw new IllegalStateException(
                    "Анализ уже запущен"
            );
        }

        run.status = "processing";
        run.stage = "classification";
        run.progress = 20;
        run.startedAt = OffsetDateTime.now();

        return new MlRequest(
                run.sourceAd.description,
                run.sourceAd.originalMc.mcId
        );
    }

    @Transactional
    public void completed(
            UUID id,
            MlResponse response
    ) {
        AnalysisRun run = runs.findById(id).orElseThrow();

        if (!"processing".equals(run.status)) {
            return;
        }

        validator.validate(
                response,
                run.sourceAd.originalMc.mcId
        );

        for (MlDraft item : response.drafts()) {

            Draft draft = new Draft();

            draft.analysis = run;

            draft.targetMc = microcategories
                    .findById(item.mcId())
                    .orElseThrow();

            draft.title = item.title();
            draft.body = item.text();
            draft.status = "generated";

            drafts.save(draft);
        }

        run.status = "completed";
        run.stage = "completed";
        run.progress = 100;
        run.finishedAt = OffsetDateTime.now();
    }

    @Transactional
    public void failed(
            UUID id,
            String code,
            String message
    ) {
        AnalysisRun run = runs.findById(id).orElseThrow();

        if ("completed".equals(run.status)) {
            return;
        }

        run.status = "failed";
        run.stage = "classification";
        run.finishedAt = OffsetDateTime.now();

        ProcessingError error = new ProcessingError();

        error.analysis = run;
        error.stage = "classification";
        error.errorCode = code;
        error.message = message;

        errors.save(error);
    }
}