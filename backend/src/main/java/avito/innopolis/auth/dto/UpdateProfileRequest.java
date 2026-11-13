package avito.innopolis.auth.dto;

import jakarta.validation.constraints.*;

import java.time.LocalDate;

public record UpdateProfileRequest(
        @NotBlank(message = "Укажите имя")
        @Size(max = 100, message = "Имя не должно превышать 100 символов")
        String firstName,
        @NotBlank(message = "Укажите фамилию")
        @Size(max = 100, message = "Фамилия не должна превышать 100 символов")
        String lastName,
        @Size(max = 100, message = "Отчество не должно превышать 100 символов")
        String middleName,
        @NotNull(message = "Укажите дату рождения")
        @Past(message = "Дата рождения должна быть в прошлом")
        LocalDate birthDate,
        @NotBlank(message = "Укажите электронную почту")
        @Email(message = "Введите корректный адрес электронной почты")
        @Size(max = 255, message = "Адрес электронной почты слишком длинный")
        String email,
        @NotBlank(message = "Укажите номер телефона")
        @Pattern(regexp = "^\\+[0-9]{10,11}$", message = "Введите телефон в формате +79991234567")
        String phone
) {}
