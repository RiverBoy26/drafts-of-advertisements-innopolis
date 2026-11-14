package avito.innopolis.ml.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.time.Duration;

@Configuration
public class MlHttpConfig {

    @Bean
    public RestClient mlRestClient(
            @Value("${ml.base-url}") String baseUrl,
            @Value("${ml.connect-timeout:3s}")
            Duration connectTimeout,
            @Value("${ml.read-timeout:120s}")
            Duration readTimeout
    ) {
        SimpleClientHttpRequestFactory factory =
                new SimpleClientHttpRequestFactory();

        factory.setConnectTimeout(connectTimeout);
        factory.setReadTimeout(readTimeout);

        return RestClient.builder()
                .baseUrl(baseUrl)
                .requestFactory(factory)
                .build();
    }
}
