package avito.innopolis.ml.client;

import avito.innopolis.ml.dto.MlRequest;
import avito.innopolis.ml.dto.MlResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.UUID;

@Component
public class MlClient {

    private final RestClient client;

    public MlClient(RestClient mlRestClient) {
        this.client = mlRestClient;
    }

    public MlResponse generate(
            UUID taskId,
            MlRequest request
    ) {
        return client.post()
                .uri("/internal/v1/avito/drafts")
                .header("X-Request-Id", taskId.toString())
                .body(request)
                .retrieve()
                .body(MlResponse.class);
    }
}