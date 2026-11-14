package avito.innopolis.ml.service;

import avito.innopolis.ml.dto.MlDraft;
import avito.innopolis.ml.dto.MlResponse;
import org.springframework.stereotype.Component;

import java.util.HashSet;
import java.util.Set;

@Component
public class MlResultValidator {

    public void validate(
            MlResponse response,
            int originalMcId
    ) {
        if (response == null || response.drafts() == null) {
            throw new IllegalArgumentException(
                    "ML вернул ответ без массива drafts"
            );
        }

        if (response.drafts().size() > 5) {
            throw new IllegalArgumentException(
                    "ML вернул более пяти целевых категорий"
            );
        }

        Set<Integer> ids = new HashSet<>();

        for (MlDraft draft : response.drafts()) {

            if (draft == null
                    || draft.mcId() == null
                    || draft.mcId() < 101
                    || draft.mcId() > 106
                    || draft.mcId() == originalMcId
                    || !ids.add(draft.mcId())) {

                throw new IllegalArgumentException(
                        "ML вернул недопустимый или повторяющийся mcId"
                );
            }

            if (draft.title() != null
                    && (draft.title().isBlank()
                    || draft.title().length() > 255)) {

                throw new IllegalArgumentException(
                        "Заголовок ML превышает 255 символов"
                );
            }

            if (draft.text() != null
                    && (draft.text().isBlank()
                    || draft.text().length() > 10000)) {

                throw new IllegalArgumentException(
                        "Текст ML превышает 10000 символов"
                );
            }
        }
    }
}