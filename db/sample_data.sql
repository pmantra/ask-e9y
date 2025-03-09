-- Insert sample organizations
INSERT INTO eligibility.organization (id, name) VALUES
(1, 'ACME Corporation'),
(2, 'Stark Industries'),
(3, 'Wayne Enterprises');

-- Insert sample files
INSERT INTO eligibility.file (id, organization_id, name, status) VALUES
(1, 1, 'acme_employees_2023.csv', 'completed'),
(2, 2, 'stark_employees_2023.csv', 'completed'),
(3, 3, 'wayne_employees_2023.csv', 'completed'),
(4, 1, 'acme_new_hires_2024.csv', 'processing');

-- Insert sample members
INSERT INTO eligibility.member (id, organization_id, file_id, first_name, last_name, email, unique_corp_id, dependent_id, date_of_birth, work_state, effective_range) VALUES
-- ACME Corporation members
(1, 1, 1, 'John', 'Doe', 'john.doe@acme.com', 'A001', '', '1980-05-15', 'CA', '[2023-01-01,)'),
(2, 1, 1, 'Jane', 'Smith', 'jane.smith@acme.com', 'A002', '', '1985-08-22', 'NY', '[2023-01-01,)'),
(3, 1, 1, 'Michael', 'Johnson', 'michael.johnson@acme.com', 'A003', '', '1975-12-10', 'TX', '[2023-01-01,)'),
(4, 1, 1, 'Emily', 'Jones', 'emily.jones@acme.com', 'A001', 'D001', '2005-04-30', 'CA', '[2023-01-01,)'),
(5, 1, 1, 'James', 'Doe', 'james.doe@acme.com', 'A001', 'D002', '2010-07-18', 'CA', '[2023-01-01,)'),

-- Stark Industries members
(6, 2, 2, 'Tony', 'Stark', 'tony@stark.com', 'S001', '', '1970-05-29', 'NY', '[2023-01-01,)'),
(7, 2, 2, 'Pepper', 'Potts', 'pepper@stark.com', 'S002', '', '1978-02-18', 'NY', '[2023-01-01,)'),
(8, 2, 2, 'Happy', 'Hogan', 'happy@stark.com', 'S003', '', '1965-11-09', 'CA', '[2023-01-01,)'),
(9, 2, 2, 'Morgan', 'Stark', 'morgan@stark.com', 'S001', 'D001', '2018-04-10', 'NY', '[2023-01-01,)'),

-- Wayne Enterprises members
(10, 3, 3, 'Bruce', 'Wayne', 'bruce@wayne.com', 'W001', '', '1972-03-30', 'NJ', '[2023-01-01,)'),
(11, 3, 3, 'Alfred', 'Pennyworth', 'alfred@wayne.com', 'W002', '', '1945-01-20', 'NJ', '[2023-01-01,)'),
(12, 3, 3, 'Lucius', 'Fox', 'lucius@wayne.com', 'W003', '', '1957-09-17', 'NJ', '[2023-01-01,)');

-- Insert sample verifications
INSERT INTO eligibility.verification (id, member_id, organization_id, unique_corp_id, dependent_id, first_name, last_name, email, date_of_birth, work_state, verification_type, verified_at) VALUES
(1, 1, 1, 'A001', '', 'John', 'Doe', 'john.doe@acme.com', '1980-05-15', 'CA', 'email', '2023-01-10 14:35:00'),
(2, 2, 1, 'A002', '', 'Jane', 'Smith', 'jane.smith@acme.com', '1985-08-22', 'NY', 'email', '2023-01-12 09:22:00'),
(3, 6, 2, 'S001', '', 'Tony', 'Stark', 'tony@stark.com', '1970-05-29', 'NY', 'email', '2023-01-05 11:15:00'),
(4, 10, 3, 'W001', '', 'Bruce', 'Wayne', 'bruce@wayne.com', '1972-03-30', 'NJ', 'email', NULL),
(5, 3, 1, 'A003', '', 'Michael', 'Johnson', 'michael.johnson@acme.com', '1975-12-10', 'TX', 'document', '2023-02-01 16:45:00');

-- Insert sample verification attempts
INSERT INTO eligibility.verification_attempt (id, verification_id, organization_id, first_name, last_name, email, verification_type, successful_verification, verified_at) VALUES
(1, 1, 1, 'John', 'Doe', 'john.doe@acme.com', 'email', true, '2023-01-10 14:35:00'),
(2, 2, 1, 'Jane', 'Smith', 'jane.smith@acme.com', 'email', true, '2023-01-12 09:22:00'),
(3, 3, 2, 'Tony', 'Stark', 'tony@stark.com', 'email', true, '2023-01-05 11:15:00'),
(4, 4, 3, 'Bruce', 'Wayne', 'bruce@wayne.com', 'email', false, NULL),
(5, 4, 3, 'Bruce', 'Wayne', 'bruce@wayne.com', 'email', false, NULL),
(6, 5, 1, 'Michael', 'Johnson', 'michael.johnson@acme.com', 'document', true, '2023-02-01 16:45:00');

-- Insert sample member verifications
INSERT INTO eligibility.member_verification (id, member_id, verification_id, verification_attempt_id) VALUES
(1, 1, 1, 1),
(2, 2, 2, 2),
(3, 6, 3, 3),
(4, 3, 5, 6);

-- Refresh materialized view
REFRESH MATERIALIZED VIEW eligibility.active_verified_members;