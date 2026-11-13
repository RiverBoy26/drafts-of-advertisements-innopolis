package avito.innopolis.analysis.service;

import avito.innopolis.analysis.dto.CreateSourceAdRequest;
import avito.innopolis.analysis.entity.AnalysisRun;
import avito.innopolis.analysis.entity.DetectedService;
import avito.innopolis.analysis.entity.ProcessingError;
import avito.innopolis.analysis.entity.SourceAd;
import avito.innopolis.analysis.repository.AnalysisRunRepository;
import avito.innopolis.analysis.repository.DetectedServiceRepository;
import avito.innopolis.analysis.repository.ProcessingErrorRepository;
import avito.innopolis.analysis.repository.SourceAdRepository;
import avito.innopolis.auth.repository.UserRepository;
import avito.innopolis.catalog.service.CatalogService;
import avito.innopolis.common.exception.ApiException;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

@Service
@Transactional(readOnly=true)
public class AnalysisService {
    private final SourceAdRepository ads;
    private final AnalysisRunRepository runs;
    private final DetectedServiceRepository detected;
    private final ProcessingErrorRepository errors;
    private final UserRepository users;
    private final CatalogService catalog;
    public AnalysisService(SourceAdRepository ads,AnalysisRunRepository runs,DetectedServiceRepository detected,ProcessingErrorRepository errors,UserRepository users,CatalogService catalog) {
        this.ads=ads;
        this.runs=runs;
        this.detected=detected;
        this.errors=errors;
        this.users=users;
        this.catalog=catalog;
    }
    public UUID userId() {
        var a=SecurityContextHolder.getContext().getAuthentication();
        if(a==null || !(a.getPrincipal() instanceof Jwt jwt))throw new ApiException(HttpStatus.UNAUTHORIZED,"UNAUTHORIZED","Требуется авторизация");
        try {
            return UUID.fromString(jwt.getSubject());
        }
        catch(Exception e) {
            throw new ApiException(HttpStatus.UNAUTHORIZED,"INVALID_TOKEN","Некорректный идентификатор пользователя");
        }
    }
    public SourceAd requireAd(UUID id) {
        return ads.findByIdAndUser_Id(id,userId()).orElseThrow(()->new ApiException(HttpStatus.NOT_FOUND,"SOURCE_AD_NOT_FOUND","Объявление не найдено"));
    }
    public AnalysisRun requireRun(UUID id) {
        return runs.findByIdAndSourceAd_User_Id(id,userId()).orElseThrow(()->new ApiException(HttpStatus.NOT_FOUND,"ANALYSIS_NOT_FOUND","Анализ не найден"));
    }
    @Transactional
    public SourceAd create(CreateSourceAdRequest r) {
    SourceAd ad=new SourceAd();
    ad.description=r.description().strip();
    ad.originalMc=catalog.require(r.mcId());
    ad.user=users.findById(userId()).orElseThrow(()->new ApiException(HttpStatus.UNAUTHORIZED,"USER_NOT_FOUND","Пользователь не найден"));
    return ads.saveAndFlush(ad);
}
public List<SourceAd> list() {
    return ads.findByUser_IdOrderByCreatedAtDesc(userId());
}
public List<AnalysisRun> runs(UUID adId) {
    requireAd(adId);
    return runs.findBySourceAd_IdOrderByCreatedAtDesc(adId);
}
public List<DetectedService> services(UUID runId) {
    requireRun(runId);
    return detected.findByAnalysis_IdOrderByCreatedAtAsc(runId);
}
public List<ProcessingError> errors(UUID runId) {
    requireRun(runId);
    return errors.findByAnalysis_IdOrderByCreatedAtAsc(runId);
}
}
