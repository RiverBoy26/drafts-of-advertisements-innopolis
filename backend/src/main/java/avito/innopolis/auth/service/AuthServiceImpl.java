
package avito.innopolis.auth.service;

import avito.innopolis.auth.dto.*;
import avito.innopolis.auth.entity.RefreshToken;
import avito.innopolis.auth.entity.Role;
import avito.innopolis.auth.entity.User;
import avito.innopolis.auth.exception.FieldConflictException;
import avito.innopolis.auth.repository.RefreshTokenRepository;
import avito.innopolis.auth.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.Base64;
import java.util.HexFormat;
import java.util.Locale;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class AuthServiceImpl implements AuthService {

    private final UserRepository userRepository;
    private final RefreshTokenRepository refreshTokenRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;

    @Value("${jwt.refresh-token-ttl}")
    private Duration refreshTokenTtl;

    private final SecureRandom secureRandom = new SecureRandom();

    @Transactional
    public AuthResponse register(RegisterRequest request) {

        String email = normalizeEmail(request.email());

        if (userRepository.existsByEmailIgnoreCase(email)) {
            throw new FieldConflictException("email", "Этот email уже зарегистрирован");
        }

        User user = new User();

        user.setFirstName(request.firstName().trim());
        user.setLastName(request.lastName().trim());
        user.setEmail(email);
        user.setPasswordHash(passwordEncoder.encode(request.password()));
        user.setRole(Role.USER);

        try {
            userRepository.saveAndFlush(user);
        } catch (DataIntegrityViolationException ex) {
            throw new ResponseStatusException(HttpStatus.CONFLICT,
                    "Email уже зарегистрирован", ex);
        }

        return createTokenPair(user);
    }

    @Transactional
    public AuthResponse login(LoginRequest request) {

        String email = normalizeEmail(request.email());

        User user = userRepository.findByEmailIgnoreCase(email)
                .orElseThrow(() -> new BadCredentialsException(
                        "Некорректный email или пароль"));

        if (!passwordEncoder.matches(request.password(), user.getPasswordHash())) {
            throw new BadCredentialsException("Некорректный email или пароль");
        }

        return createTokenPair(user);
    }

    @Transactional
    public AuthResponse refresh(RefreshRequest request) {

        String hash = hashToken(request.refreshToken());

        RefreshToken storedToken = refreshTokenRepository.findByTokenHashForUpdate(hash)
                .orElseThrow(() -> new BadCredentialsException(
                        "Некорректный refresh token"));

        if (storedToken.getRevokedAt() != null) {
            throw new BadCredentialsException("Токен обновления был отозван");
        }

        if (!storedToken.getExpiresAt().isAfter(LocalDateTime.now())) {
            throw new BadCredentialsException("Истек срок действия токена обновления");
        }

        storedToken.setRevokedAt(LocalDateTime.now());

        return createTokenPair(storedToken.getUser());
    }

    @Transactional
    public void logout(LogoutRequest request) {

        String hash = hashToken(request.refreshToken());

        refreshTokenRepository.findByTokenHashForUpdate(hash)
                .ifPresent(token -> {
                    if (token.getRevokedAt() == null) {
                        token.setRevokedAt(LocalDateTime.now());
                    }
                });
    }

    @Transactional(readOnly = true)
    public UserResponse getCurrentUser(UUID userId) {

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new ResponseStatusException(
                                HttpStatus.NOT_FOUND, "Пользователь не найден"));

        return UserResponse.from(user);
    }

    private AuthResponse createTokenPair(User user) {

        String accessToken = jwtService.generateAccessToken(user);

        String refreshToken = generateRefreshToken();

        RefreshToken token = new RefreshToken();

        token.setUser(user);
        token.setTokenHash(hashToken(refreshToken));
        token.setExpiresAt(LocalDateTime.now().plus(refreshTokenTtl));

        refreshTokenRepository.save(token);

        return new AuthResponse(
                accessToken,
                refreshToken,
                "Bearer",
                jwtService.getAccessTokenTtlSeconds(),
                UserResponse.from(user)
        );
    }

    private String generateRefreshToken() {

        byte[] randomBytes = new byte[32];
        secureRandom.nextBytes(randomBytes);

        return Base64.getUrlEncoder().withoutPadding().encodeToString(randomBytes);
    }

    private String hashToken(String token) {

        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");

            byte[] hash = digest.digest(token.getBytes(StandardCharsets.UTF_8));

            return HexFormat.of().formatHex(hash);

        } catch (java.security.NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 недоступен", ex);
        }
    }

    private String normalizeEmail(String email) {
        return email.trim().toLowerCase(Locale.ROOT);
    }


    @Transactional
    public UserResponse updateCurrentUser(
            UUID userId,
            UpdateProfileRequest request
    ) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.NOT_FOUND,
                        "Пользователь не найден"
                ));

        String email = normalizeEmail(request.email());

        if (userRepository.existsByEmailIgnoreCaseAndIdNot(
                email, userId
        )) {
            throw new FieldConflictException("email", "Этот email уже используется");
        }


        user.setFirstName(request.firstName().trim());
        user.setLastName(request.lastName().trim());
        user.setEmail(email);

        try {
            return UserResponse.from(userRepository.saveAndFlush(user));
        } catch (DataIntegrityViolationException ex) {
            throw new ResponseStatusException(
                    HttpStatus.CONFLICT,
                    "Email уже используется",
                    ex
            );
        }
    }
}
