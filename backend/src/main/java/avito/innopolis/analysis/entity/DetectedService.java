package avito.innopolis.analysis.entity;

import jakarta.persistence.*;
import org.hibernate.annotations.CreationTimestamp;
import avito.innopolis.catalog.entity.Microcategory;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.UUID;

@Entity
@Table(name="detected_services", indexes={@Index(name="idx_detected_analysis",columnList="analysis_id")})
public class DetectedService {
    @Id
    @GeneratedValue(strategy=GenerationType.UUID)
    public UUID id;

    @ManyToOne(fetch=FetchType.LAZY,optional=false)
    @JoinColumn(name="analysis_id",nullable=false)
    public AnalysisRun analysis;
    @ManyToOne(fetch=FetchType.LAZY,optional=false)
    @JoinColumn(name="target_mc_id",nullable=false)
    public Microcategory targetMc;
    @Column(nullable=false,length=255)
    public String serviceName;
    @Column(nullable=false,columnDefinition="text")
    public String sourceFragment;
    @Column(precision=5,scale=4)
    public BigDecimal confidence;
    @Column(nullable=false)
    public boolean confirmed=false;
    @CreationTimestamp
    @Column(nullable=false,updatable=false)
    public OffsetDateTime createdAt;
 @PrePersist @PreUpdate
 protected void validateTarget(){
   if(analysis!=null && analysis.sourceAd!=null && analysis.sourceAd.originalMc!=null && targetMc!=null
      && java.util.Objects.equals(analysis.sourceAd.originalMc.mcId,targetMc.mcId))
    throw new IllegalStateException("Нельзя создавать дополнительную услугу/черновик для исходной микрокатегории");
 }
}
