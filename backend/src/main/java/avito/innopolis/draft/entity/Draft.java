package avito.innopolis.draft.entity;

import avito.innopolis.analysis.entity.AnalysisRun;
import avito.innopolis.catalog.entity.Microcategory;
import jakarta.persistence.*;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.OffsetDateTime;
import java.util.UUID;

@Entity
@Table(name="drafts",uniqueConstraints=@UniqueConstraint(name="uk_draft_analysis_target",columnNames={"analysis_id","target_mc_id"}),indexes={@Index(name="idx_draft_analysis",columnList="analysis_id")})
public class Draft {
    @Id @GeneratedValue(strategy=GenerationType.UUID)
    public UUID id;

    @ManyToOne(fetch=FetchType.LAZY,optional=false)
    @JoinColumn(name="analysis_id",nullable=false)
    public AnalysisRun analysis;

    @ManyToOne(fetch=FetchType.LAZY,optional=false)
    @JoinColumn(name="target_mc_id",nullable=false)
    public Microcategory targetMc;

    @Column(length=255)
    public String title;

    @Column(name="body",columnDefinition="text")
    public String body;

    @Column(nullable=false,length=32)
    public String status="generated";

    @CreationTimestamp @Column(nullable=false,updatable=false)
    public OffsetDateTime createdAt;

    @UpdateTimestamp @Column(nullable=false)
    public OffsetDateTime updatedAt;

    @PrePersist @PreUpdate
    protected void validateTarget() {
        if(analysis!=null && analysis.sourceAd!=null && analysis.sourceAd.originalMc!=null && targetMc!=null
        && java.util.Objects.equals(analysis.sourceAd.originalMc.mcId,targetMc.mcId))
        throw new IllegalStateException("Нельзя создавать дополнительную услугу/черновик для исходной микрокатегории");
    }
}
