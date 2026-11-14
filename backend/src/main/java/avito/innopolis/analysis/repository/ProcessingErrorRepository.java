package avito.innopolis.analysis.repository;

import avito.innopolis.analysis.entity.ProcessingError;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface ProcessingErrorRepository extends JpaRepository<ProcessingError,UUID> {
 List<ProcessingError> findByAnalysis_IdOrderByCreatedAtAsc(UUID id);
}
