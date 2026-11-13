package avito.innopolis.auth.repository;

import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import avito.innopolis.auth.entity.RefreshToken;

import java.util.Optional;
import java.util.UUID;

public interface RefreshTokenRepository extends JpaRepository<RefreshToken, UUID> {
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("""
        SELECT t
        FROM RefreshToken t
        JOIN FETCH t.user
        WHERE t.tokenHash = :hash
        """)
    Optional<RefreshToken> findByTokenHashForUpdate(@Param("hash") String hash);
}
