package avito.innopolis.analysis.entity;

import jakarta.persistence.*;
import org.hibernate.annotations.CreationTimestamp;

import java.time.OffsetDateTime;
import java.util.UUID;

@Entity
@Table(name="processing_errors",indexes={@Index(name="idx_errors_analysis",columnList="analysis_id")})
public class ProcessingError {
    @Id
    @GeneratedValue(strategy=GenerationType.UUID)
    public UUID id;
    @ManyToOne(fetch=FetchType.LAZY,optional=false)
    @JoinColumn(name="analysis_id",nullable=false)
    public AnalysisRun analysis;
    @Column(nullable=false,length=40)
    public String stage;
    @Column(nullable=false,length=80)
    public String errorCode;
    @Column(nullable=false,columnDefinition="text")
    public String message;
    @CreationTimestamp
    public OffsetDateTime createdAt;
}
