package avito.innopolis.auth.service;

import avito.innopolis.auth.entity.User;

public interface JwtService {
    String generateAccessToken(User user);

    long getAccessTokenTtlSeconds();
}
