package avito.innopolis.ml.client;

import avito.innopolis.ml.dto.MlRequest;
import avito.innopolis.ml.dto.MlResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.UUID;

@Component
public class MlClient {

    private final RestClient client;
    private final String internalApiToken;

    public MlClient(RestClient mlRestClient, @Value("${ml.internal-api-token:}") String internalApiToken) {
        this.client = mlRestClient;
        this.internalApiToken = internalApiToken;
    }

    public MlResponse generate(
            UUID taskId,
            MlRequest request
    ) {
        RestClient.RequestBodySpec call = client.post()
                .uri("/internal/v1/avito/drafts")
                .header("X-Request-Id", taskId.toString());
        if (!internalApiToken.isBlank()) {
            call.header("Authorization", "Bearer " + internalApiToken);
        }
        return call.body(request)
                .retrieve()
                .body(MlResponse.class);
    }
}
