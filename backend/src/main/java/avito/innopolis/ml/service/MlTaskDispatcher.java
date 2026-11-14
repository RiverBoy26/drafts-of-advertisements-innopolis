package avito.innopolis.ml.service;

import avito.innopolis.ml.client.MlClient;
import avito.innopolis.ml.dto.MlRequest;
import avito.innopolis.ml.dto.MlResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.client.RestClientException;

import java.util.UUID;

@Service
public class MlTaskDispatcher {

    private static final Logger log =
            LoggerFactory.getLogger(MlTaskDispatcher.class);

    private final MlClient client;
    private final MlTaskPersistence persistence;

    public MlTaskDispatcher(
            MlClient client,
            MlTaskPersistence persistence
    ) {
        this.client = client;
        this.persistence = persistence;
    }

    @Async("mlTaskExecutor")
    public void dispatch(UUID id) {
        try {
            MlRequest input = persistence.begin(id);

            MlResponse output = client.generate(id, input);

            persistence.completed(id, output);

        } catch (ResourceAccessException ex) {

            log.warn(
                    "ML connection/timeout failed for task {}: {}",
                    id,
                    ex.toString()
            );

            persistence.failed(
                    id,
                    "ML_UNAVAILABLE",
                    "Нет соединения с ML-сервисом "
                            + "или превышено время ожидания"
            );

        } catch (RestClientResponseException ex) {

            log.warn(
                    "ML HTTP error for task {}: HTTP {}",
                    id,
                    ex.getStatusCode()
            );

            String code =
                    ex.getStatusCode().value() == 504
                            ? "ML_TIMEOUT"
                            : "ML_SERVICE_ERROR";

            persistence.failed(
                    id,
                    code,
                    "ML-сервис вернул HTTP "
                            + ex.getStatusCode().value()
            );

        } catch (RestClientException ex) {

            log.error(
                    "ML response decode failed for task {}",
                    id,
                    ex
            );

            persistence.failed(
                    id,
                    "ML_INVALID_RESPONSE",
                    "Некорректный JSON-ответ ML-сервиса"
            );

        } catch (Exception ex) {

            log.error("ML task {} failed", id, ex);

            String code =
                    ex instanceof IllegalArgumentException
                            ? "ML_INVALID_RESPONSE"
                            : "ML_PROCESSING_ERROR";

            persistence.failed(
                    id,
                    code,
                    "Не удалось обработать ответ ML-сервиса"
            );
        }
    }
}