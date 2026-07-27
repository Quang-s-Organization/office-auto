# CƠ SỞ LÝ THUYẾT


## Tầm quan trọng dữ liệu ảnh huấn luyện trong thị giác máy tính


Thị giác máy tính (Computer Vision) là lĩnh vực nghiên cứu nhằm trang bị cho máy tính khả năng tiếp nhận, xử lý và diễn giải thông tin từ thế giới trực quan, bao gồm hình ảnh tĩnh, video và luồng cảm biến đa phương thức. Không giống các hệ thống luật chuyên gia dựa trên quy tắc cứng, các mô hình thị giác máy tính hiện đại học biểu diễn đặc trưng trực tiếp từ dữ liệu thông qua quá trình tối ưu hóa tham số, khiến chất lượng và quy mô của tập dữ liệu ảnh huấn luyện trở thành yếu tố quyết định hiệu năng tổng thể của mô hình [1]. Điều này đặt ra một nghịch lý trung tâm trong nghiên cứu: khả năng nhận diện của mô hình chỉ tốt bằng phân phối thống kê của dữ liệu mà nó đã thấy trong quá trình huấn luyện, và bất kỳ thiên kiến hay thiếu sót nào trong tập dữ liệu đều sẽ được khuếch đại trong hành vi suy luận (inference behavior) cuối cùng.


Các mô hình học sâu (Deep Learning) cho thị giác máy tính, đặc biệt là mạng tích chập (Convolutional Neural Network - CNN) và Transformer thị giác (Vision Transformer - ViT), đã đạt được kết quả vượt trội trên nhiều tác vụ chuẩn kể từ thành công đột phá của AlexNet năm 2012 trên tập dữ liệu ImageNet với hơn một triệu hai trăm nghìn ảnh thuộc một nghìn lớp đối tượng [1]. Bản chất của học sâu là tối ưu hóa hàng triệu tham số trên không gian gradient có chiều cao, đòi hỏi lượng dữ liệu lớn để tránh overfitting và để mô hình học được các biểu diễn bất biến (invariant representations) đủ tổng quát cho dữ liệu chưa thấy bao giờ. Quy luật scaling được nghiên cứu bởi Zhai và cộng sự năm 2022 cho thấy hiệu năng mô hình tăng theo hàm lũy thừa với số lượng dữ liệu huấn luyện, với hệ số mũ dao động từ 0.1 đến 0.4 tùy thuộc vào kiến trúc và tác vụ cụ thể, điều này lý giải tại sao các tổ chức nghiên cứu hàng đầu như Google và Meta liên tục đầu tư vào việc mở rộng quy mô tập dữ liệu của mình [2].

Quan hệ scaling này có thể được biểu diễn dưới dạng hàm lũy thừa của sai số kiểm tra theo số lượng mẫu huấn luyện:

$$\mathcal{E}(N) \;\approx\; \mathcal{E}_{\infty} + c \cdot N^{-\alpha}, \qquad \alpha \in [0.1,\ 0.4]$$

trong đó $\mathcal{E}(N)$ là sai số kỳ vọng khi huấn luyện với $N$ mẫu, $\mathcal{E}_{\infty}$ là sai số không thể giảm (irreducible error) do nhiễu nội tại của bài toán, $c$ là hằng số tỉ lệ và $\alpha$ là hệ số mũ scaling đặc trưng cho kiến trúc và tác vụ. Hệ số $\alpha$ càng lớn thì lợi ích biên của việc bổ sung dữ liệu càng cao.

[Hình 1.1. Các bước xây dựng mô hình học máy trong thị giác máy tính]

Chất lượng dữ liệu ảnh không chỉ được đo bằng số lượng mà còn bởi tính đa dạng (diversity), sự cân bằng phân lớp (class balance), độ chính xác nhãn (label accuracy) và tính đại diện cho phân phối dữ liệu triển khai thực tế. Một tập dữ liệu lớn nhưng thiếu đa dạng về góc chụp, điều kiện ánh sáng và bối cảnh nền sẽ tạo ra mô hình chỉ hoạt động tốt trong môi trường phòng thí nghiệm nhưng thất bại nghiêm trọng khi gặp điều kiện ngoài phân phối (out-of-distribution). Ngược lại, một tập dữ liệu nhỏ nhưng được curate cẩn thận với nhãn chất lượng cao và phân phối đa dạng có thể vượt trội hơn tập dữ liệu lớn được thu thập tự động không qua kiểm duyệt, đặc biệt rõ rệt trong các tác vụ phân đoạn ngữ nghĩa (semantic segmentation) và phát hiện đối tượng (object detection) nơi chú thích chi tiết ở mức pixel [2].


## Các thách thức phổ biến liên quan đến dữ liệu


Xây dựng tập dữ liệu ảnh huấn luyện chất lượng cao phải đối mặt với một loạt thách thức kỹ thuật và thực tiễn có tính hệ thống, trong đó ba nhóm thách thức lớn nhất là mất cân bằng phân lớp, ô nhiễm nhãn và sự dịch chuyển phân phối. Mất cân bằng phân lớp (class imbalance) xảy ra khi tần suất xuất hiện các lớp trong tập dữ liệu không phản ánh phân phối thực tế của bài toán ứng dụng, dẫn đến mô hình có xu hướng thiên về lớp đa số và bỏ sót các lớp thiểu số có tầm quan trọng cao về mặt ứng dụng [3]. Điều này đặc biệt nghiêm trọng trong các bài toán y tế như phát hiện ung thư hoặc dị thường tim mạch, nơi tỷ lệ ca dương tính chỉ chiếm từ một đến năm phần trăm tổng số mẫu nhưng lại là chính xác những trường hợp cần được phát hiện đúng nhất. Các phương pháp xử lý bao gồm oversampling tổng hợp như SMOTE (Synthetic Minority Oversampling Technique) cho dữ liệu ảnh, class-weighted loss function và focal loss được giới thiệu trong nghiên cứu RetinaNet để chú trọng vào các mẫu khó trong quá trình tối ưu hóa [3].

SMOTE tạo mẫu thiểu số mới bằng cách nội suy tuyến tính giữa một mẫu gốc $x_i$ và một trong các láng giềng gần nhất $x_{nn}$ của nó trong không gian đặc trưng:

$$x_{\text{new}} = x_i + \delta\,(x_{nn} - x_i), \qquad \delta \sim \mathcal{U}(0,1)$$

Trong khi đó, focal loss định nghĩa lại hàm mất mát entropy chéo bằng cách thêm một hệ số điều biến $(1 - p_t)^{\gamma}$ để giảm trọng số đóng góp của các mẫu dễ và dồn sự chú ý vào các mẫu khó:

$$\mathrm{FL}(p_t) = -\,\alpha_t\,(1 - p_t)^{\gamma}\,\log(p_t)$$

trong đó $p_t$ là xác suất dự đoán cho lớp đúng, $\gamma \ge 0$ là tham số tập trung (focusing parameter, thường lấy $\gamma = 2$) và $\alpha_t$ là trọng số cân bằng lớp. Khi $\gamma = 0$, focal loss suy biến về entropy chéo có trọng số thông thường.


Ô nhiễm nhãn (label noise) là thách thức thứ hai, xuất hiện khi nhãn được gán không chính xác do sự mơ hồ về định nghĩa lớp, lỗi người chú thích hoặc sự không nhất quán giữa nhiều người chú thích khác nhau. Nghiên cứu của Northcutt và cộng sự năm 2021 về tập dữ liệu ImageNet ước tính rằng khoảng 3,4 phần trăm trong một triệu nhãn kiểm tra có lỗi hệ thống, một tỷ lệ tưởng chừng nhỏ nhưng đủ để làm lệch hướng quá trình tối ưu hóa khi nhân với số lượng mẫu khổng lồ [3]. Các kỹ thuật học mạnh mẽ với nhãn nhiễu (learning with noisy labels) như Co-teaching, MentorNet và Label Smoothing đã được phát triển để giảm thiểu ảnh hưởng của nhãn sai, trong đó Co-teaching huấn luyện song song hai mạng để chúng có thể lọc ra các mẫu có khả năng nhãn sai cao trước khi cập nhật gradient. Ngoài ra, phương pháp crowdsourced labeling kết hợp với quy tắc đa số có trọng số chuyên môn đang dần được áp dụng rộng rãi để nâng cao chất lượng chú thích ở quy mô lớn mà vẫn kiểm soát được chi phí.


Sự dịch chuyển phân phối (distribution shift) hay còn gọi là domain shift là khi phân phối dữ liệu huấn luyện khác biệt đáng kể so với phân phối dữ liệu triển khai thực tế, dẫn đến sự suy giảm hiệu năng đột ngột của mô hình khi ra ngoài môi trường phòng thí nghiệm [4]. Chẳng hạn, một mô hình nhận diện biển báo giao thông được huấn luyện hoàn toàn trên ảnh ban ngày điều kiện thời tiết tốt sẽ thất bại khi gặp ảnh chụp vào ban đêm, trong mưa hoặc dưới ánh đèn đường. Domain shift có thể xuất hiện theo nhiều dạng: covariate shift khi phân phối đầu vào thay đổi nhưng quan hệ đầu vào-đầu ra giữ nguyên, concept drift khi chính bản chất của bài toán thay đổi theo thời gian, và prior probability shift khi tỷ lệ các lớp thay đổi giữa môi trường huấn luyện và triển khai. Các phương pháp thích ứng miền (domain adaptation) như DANN (Domain-Adversarial Neural Network) và các kỹ thuật học chuyển giao (transfer learning) được thiết kế để giảm khoảng cách phân phối này, nhưng hiệu quả phụ thuộc nhiều vào mức độ tương đồng giữa hai miền và chất lượng dữ liệu miền đích [4].

Bảng dưới đây tóm tắt ba nhóm thách thức dữ liệu cốt lõi cùng biểu hiện đặc trưng và hướng xử lý tương ứng.

| Thách thức | Biểu hiện điển hình | Phương pháp xử lý tiêu biểu |
|---|---|---|
| Mất cân bằng phân lớp | Lớp thiểu số quan trọng chỉ chiếm 1–5% mẫu; mô hình thiên về lớp đa số | SMOTE, class-weighted loss, focal loss |
| Ô nhiễm nhãn | Nhãn sai do mơ hồ định nghĩa hoặc bất đồng giữa người chú thích (~3,4% nhãn ImageNet) | Co-teaching, MentorNet, Label Smoothing, đa số có trọng số chuyên môn |
| Dịch chuyển phân phối | Hiệu năng sụt giảm khi gặp điều kiện ngoài phân phối (đêm, mưa, miền mới) | DANN, transfer learning, domain adaptation |


Thách thức về chi phí và tốc độ thu thập dữ liệu cũng đóng vai trò then chốt, đặc biệt trong các lĩnh vực chuyên sâu như y tế, tự động hóa công nghiệp và hàng không vũ trụ, nơi mỗi ảnh cần được chú thích bởi chuyên gia có trình độ cao với chi phí lên đến hàng chục đô la cho một ảnh duy nhất [3]. Vấn đề quyền riêng tư và đạo đức dữ liệu cũng ngày càng trở nên quan trọng khi dữ liệu ảnh có thể chứa thông tin nhận dạng cá nhân, đặt ra yêu cầu tuân thủ các quy định như GDPR ở Châu Âu và Luật Bảo vệ Dữ liệu Cá nhân tại Việt Nam. Sự kết hợp của các thách thức này thúc đẩy mạnh mẽ nhu cầu về các phương pháp sinh dữ liệu tổng hợp có kiểm soát, vừa giải quyết bài toán quy mô vừa bảo đảm tính đa dạng và an toàn về quyền riêng tư.


## Các lĩnh vực ứng dụng chính


Thị giác máy tính với nền tảng dữ liệu ảnh chất lượng cao đang tạo ra tác động chuyển đổi sâu rộng trong nhiều lĩnh vực kinh tế và xã hội, trong đó ba lĩnh vực dẫn đầu về mức độ ứng dụng và giá trị tạo ra là y tế, sản xuất công nghiệp và phương tiện tự lái. Trong y tế, hệ thống phân tích ảnh y khoa ứng dụng học sâu đã đạt và trong nhiều trường hợp vượt qua độ chính xác chẩn đoán của bác sĩ chuyên khoa đối với một số bệnh cụ thể, tiêu biểu nhất là nghiên cứu của Esteva và cộng sự năm 2017 trên tập dữ liệu 129,450 ảnh da liễu cho thấy mạng tích chập đạt độ chính xác phân loại ung thư da tương đương với hội đồng 21 bác sĩ da liễu được chứng nhận [5]. Các ứng dụng bao gồm phân tích ảnh X-quang ngực, phát hiện bệnh võng mạc đái tháo đường qua ảnh đáy mắt, phân đoạn khối u trong ảnh MRI và CT, và phân tích mẫu bệnh học từ ảnh tiêu bản vi thể số. Điểm mấu chốt về dữ liệu trong lĩnh vực này là mỗi nhãn chú thích cần được xác nhận bởi ít nhất hai chuyên gia y tế và có quy trình giải quyết bất đồng ý kiến rõ ràng, đồng thời dữ liệu phải đại diện đầy đủ cho sự đa dạng về nhân khẩu học, thiết bị chụp ảnh và giai đoạn bệnh lý để tránh thiên kiến chẩn đoán hệ thống [5].


Sản xuất công nghiệp và kiểm soát chất lượng tự động là lĩnh vực thứ hai hưởng lợi đáng kể từ sự tiến bộ trong dữ liệu ảnh và mô hình thị giác máy tính. Hệ thống phát hiện lỗi bề mặt (surface defect detection) trong dây chuyền sản xuất điện tử, ô tô và dệt may có thể vận hành liên tục với tốc độ vượt xa khả năng kiểm tra thủ công của con người, xử lý hàng nghìn sản phẩm mỗi giờ trong điều kiện ánh sáng và góc chụp kiểm soát chặt chẽ [6]. Tuy nhiên, một trong những thách thức đặc thù của lĩnh vực này là sự hiếm gặp cực kỳ của các mẫu lỗi trong sản xuất thực tế, khi tỷ lệ sản phẩm lỗi chỉ ở mức phần nghìn đến phần triệu, dẫn đến vấn đề mất cân bằng phân lớp nghiêm trọng và đòi hỏi các kỹ thuật sinh dữ liệu lỗi tổng hợp để đảm bảo mô hình được huấn luyện trên đủ mẫu dương tính. Nghiên cứu của MVTec Anomaly Detection dataset đã cung cấp chuẩn so sánh được chấp nhận rộng rãi trong cộng đồng, gồm 5,354 ảnh độ phân giải cao thuộc mười lăm loại vật liệu và đối tượng khác nhau với tổng cộng 70 loại lỗi được chú thích ở mức pixel.


Phương tiện tự lái và hệ thống hỗ trợ lái xe nâng cao (Advanced Driver Assistance Systems - ADAS) là một trong những ứng dụng đòi hỏi tập dữ liệu ảnh đa dạng và phong phú nhất hiện nay, với yêu cầu bao phủ đầy đủ mọi điều kiện thời tiết, thời gian trong ngày, loại đường, mật độ giao thông và tình huống biên hiếm gặp nhưng an toàn tới hạn [6]. Bộ dữ liệu Waymo Open Dataset với hơn ba nghìn phút lái xe được ghi lại bởi 32 cảm biến LiDAR và 5 camera, tập dữ liệu KITTI của Viện Công nghệ Karlsruhe và nuScenes của Motional đã trở thành nền tảng chuẩn cho nghiên cứu phát hiện đối tượng 3D và ước lượng độ sâu. Đáng chú ý là các tình huống long-tail, tức là các trường hợp hiếm gặp như người đi bộ ở điều kiện tầm nhìn thấp, phương tiện bị che khuất một phần hoặc điều kiện thời tiết cực đoan, chiếm lượng không đáng kể trong dữ liệu tự nhiên nhưng lại chính xác là những trường hợp quyết định sự an toàn trong thực tế, và đây là một trong những động lực mạnh mẽ nhất thúc đẩy nghiên cứu sinh dữ liệu ảnh tổng hợp.


Nông nghiệp thông minh và giám sát môi trường là lĩnh vực ứng dụng đang thu hút đầu tư mạnh mẽ, đặc biệt trong bối cảnh biến đổi khí hậu và áp lực an ninh lương thực toàn cầu. Các hệ thống phân tích ảnh chụp từ UAV (drone) và vệ tinh viễn thám được ứng dụng để phát hiện sâu bệnh, đánh giá tình trạng sức khỏe cây trồng qua chỉ số thực vật NDVI (Normalized Difference Vegetation Index), ước lượng năng suất thu hoạch và giám sát diện tích rừng. Chỉ số NDVI được tính từ phản xạ ở dải cận hồng ngoại và dải đỏ theo công thức:

$$\mathrm{NDVI} = \frac{\rho_{\text{NIR}} - \rho_{\text{RED}}}{\rho_{\text{NIR}} + \rho_{\text{RED}}}$$

trong đó $\rho_{\text{NIR}}$ và $\rho_{\text{RED}}$ lần lượt là giá trị phản xạ phổ ở dải cận hồng ngoại và dải đỏ; giá trị NDVI nằm trong khoảng $[-1, 1]$, với giá trị càng cao thể hiện mật độ và sức khỏe thực vật càng tốt. Thách thức dữ liệu đặc trưng của lĩnh vực này bao gồm sự biến đổi theo mùa vụ và địa lý, nhu cầu chú thích chuyên môn từ các nhà nông học và sinh thái học, cùng với độ phân giải không gian và phổ ảnh đa dạng phụ thuộc vào loại cảm biến thu thập [5].

Bảng sau đối chiếu các lĩnh vực ứng dụng chính theo bộ dữ liệu tiêu biểu và thách thức dữ liệu đặc thù.

| Lĩnh vực | Bộ dữ liệu / chuẩn tiêu biểu | Thách thức dữ liệu đặc thù |
|---|---|---|
| Y tế | 129,450 ảnh da liễu (Esteva 2017); ảnh X-quang, đáy mắt, MRI/CT | Cần ≥2 chuyên gia xác nhận nhãn; đa dạng nhân khẩu học và thiết bị |
| Sản xuất công nghiệp | MVTec AD (5,354 ảnh, 15 loại, 70 loại lỗi) | Mẫu lỗi cực hiếm (phần nghìn–phần triệu); mất cân bằng nghiêm trọng |
| Phương tiện tự lái | Waymo Open, KITTI, nuScenes | Tình huống long-tail an toàn tới hạn; phủ mọi điều kiện thời tiết/ánh sáng |
| Nông nghiệp & môi trường | Ảnh UAV và vệ tinh viễn thám; chỉ số NDVI | Biến đổi theo mùa vụ/địa lý; đa dạng độ phân giải không gian và phổ |


## Các phương pháp sinh dữ liệu ảnh truyền thống


Trước sự phát triển của các phương pháp sinh tổng hợp dựa trên học sâu, cộng đồng nghiên cứu và phát triển ứng dụng thị giác máy tính chủ yếu dựa vào hai nhóm phương pháp truyền thống để xây dựng và mở rộng tập dữ liệu ảnh: thu thập thủ công kết hợp chú thích của con người và tăng cường dữ liệu thông qua các biến đổi hình học và quang học xác định. Hai nhóm phương pháp này đã tạo ra nền tảng cho nhiều đột phá quan trọng trong lịch sử thị giác máy tính, từ ImageNet đến COCO, và tiếp tục đóng vai trò quan trọng như nguồn dữ liệu gốc cho các hệ thống huấn luyện hiện đại ngay cả khi được kết hợp với dữ liệu tổng hợp [7].


### Thu thập dữ liệu ảnh thủ công


Thu thập dữ liệu ảnh thủ công là phương pháp xây dựng tập dữ liệu nguyên thủy nhất và vẫn là nguồn dữ liệu có tính xác thực cao nhất khi được thực hiện đúng cách, bao gồm quy trình lập kế hoạch thu thập, chụp ảnh thực địa có kiểm soát và chú thích chuyên môn bởi con người. Quy trình thu thập hiệu quả bắt đầu từ việc xác định rõ phân phối đích của tập dữ liệu thông qua phân tích ontology đối tượng, sau đó thiết kế giao thức thu thập đảm bảo sự đa dạng theo các chiều quan trọng như góc nhìn, điều kiện ánh sáng, nền và kích thước đối tượng trong ảnh [7]. Tập dữ liệu ImageNet, được xây dựng bởi nhóm nghiên cứu của Fei-Fei Li tại Stanford từ năm 2007 đến 2009, đã huy động hơn ba mươi nghìn người chú thích qua nền tảng Amazon Mechanical Turk để tạo ra 14 triệu ảnh thuộc 21,841 nhóm đối tượng theo WordNet hierarchy, thiết lập chuẩn vàng cho phương pháp thu thập dữ liệu ảnh quy mô lớn [1].


Quy trình chú thích (annotation pipeline) là yếu tố quyết định chất lượng của tập dữ liệu thu thập thủ công, đặc biệt với các tác vụ cần chú thích chi tiết như phát hiện đối tượng với bounding box, phân đoạn instance với mask ở mức pixel và ước lượng pose với keypoint. Tập dữ liệu COCO (Common Objects in Context) do Microsoft phát triển đã đặt ra chuẩn mực cho quy trình chú thích đa tác vụ, với 330,000 ảnh được chú thích bởi hơn năm mươi nghìn người, trong đó mỗi ảnh trung bình chứa 7.7 đối tượng được chú thích với bounding box, mask phân đoạn và 80 loại nhãn phân cấp [2]. Công cụ chú thích hiện đại như CVAT (Computer Vision Annotation Tool), Label Studio và Scale AI cung cấp hạ tầng quản lý tác vụ, kiểm soát chất lượng nhiều lớp và tích hợp dự đoán trợ giúp từ mô hình pre-trained để tăng tốc quá trình chú thích từ hai đến năm lần so với chú thích thuần thủ công. Các hệ thống Inter-Annotator Agreement (IAA) như Cohen's Kappa và Fleiss' Kappa được sử dụng để đo lường mức độ đồng thuận giữa các người chú thích, với ngưỡng chấp nhận thường được đặt ở kappa lớn hơn 0.7 cho tác vụ phân loại và lớn hơn 0.6 cho tác vụ phân đoạn [7].

Hệ số Cohen's Kappa được định nghĩa nhằm hiệu chỉnh phần đồng thuận có thể xảy ra do ngẫu nhiên:

$$\kappa = \frac{p_o - p_e}{1 - p_e}$$

trong đó $p_o$ là tỉ lệ đồng thuận quan sát được giữa hai người chú thích và $p_e$ là tỉ lệ đồng thuận kỳ vọng nếu họ gán nhãn một cách ngẫu nhiên độc lập. Giá trị $\kappa = 1$ ứng với đồng thuận tuyệt đối, $\kappa = 0$ ứng với mức đồng thuận không hơn ngẫu nhiên.

Bảng sau so sánh ba bộ dữ liệu chú thích thủ công kinh điển theo quy mô và đặc điểm chú thích.

| Bộ dữ liệu | Quy mô ảnh | Số lớp / nhãn | Loại chú thích |
|---|---|---|---|
| ImageNet | 14 triệu | 21,841 nhóm (WordNet) | Nhãn phân loại cấp ảnh |
| COCO | 330,000 | 80 lớp; ~7.7 đối tượng/ảnh | Bounding box, mask phân đoạn, keypoint |
| Cityscapes | Cảnh đường phố đô thị | 30 lớp ngữ nghĩa | Phân đoạn pixel-level (~1.5 giờ/ảnh) |


Chi phí và thời gian là rào cản lớn nhất của phương pháp thu thập thủ công khi mở rộng quy mô. Ước tính của Cordts và cộng sự trong dự án Cityscapes cho biết chi phí trung bình để chú thích một ảnh đường phố ở mức semantic segmentation với mask pixel-level là 1.5 giờ lao động chuyên môn, tức là hàng nghìn giờ người cho một tập dữ liệu cỡ vừa, chưa kể chi phí thiết bị, logistics và kiểm soát chất lượng [7]. Bên cạnh đó, nhiều ứng dụng có yêu cầu chụp ảnh trong điều kiện khó tiếp cận hoặc nguy hiểm như bên trong lò phản ứng hạt nhân, dưới nước sâu hoặc trong vùng thảm họa tự nhiên, khiến việc thu thập dữ liệu thực tế trở nên không khả thi hoặc cực kỳ tốn kém. Những hạn chế cốt lõi này, kết hợp với nhu cầu dữ liệu ngày càng tăng của các kiến trúc học sâu hiện đại, chính là động lực thúc đẩy sự phát triển mạnh mẽ của các phương pháp tăng cường và sinh dữ liệu tổng hợp.


### Tăng cường dữ liệu ảnh


Tăng cường dữ liệu ảnh (data augmentation) là nhóm kỹ thuật áp dụng các biến đổi có kiểm soát lên ảnh gốc để tạo ra các biến thể mới, qua đó mở rộng hiệu quả quy mô của tập dữ liệu mà không cần thu thập thêm dữ liệu thực và đồng thời cải thiện khả năng tổng quát hóa của mô hình bằng cách mô phỏng sự biến thiên tự nhiên của dữ liệu thực [8]. Về mặt lý thuyết, tăng cường dữ liệu có thể được hiểu là một dạng regularization ngầm ẩn, áp đặt tiên nghiệm về tính bất biến mong muốn của mô hình (invariance prior) lên không gian biểu diễn học được. Khi chúng ta áp dụng phép lật ngang ảnh (horizontal flip) trong huấn luyện, chúng ta ngầm yêu cầu mô hình học biểu diễn bất biến với phản xạ gương, một tiên nghiệm hợp lý cho nhiều tác vụ nhận dạng đối tượng nhưng hoàn toàn không phù hợp cho tác vụ nhận dạng ký tự chữ viết tay hay phân biệt trái-phải trong chẩn đoán y khoa [8].


Các kỹ thuật tăng cường hình học bao gồm lật ảnh theo chiều ngang và dọc, xoay ảnh một góc tùy ý, cắt ngẫu nhiên (random crop), biến dạng phi tuyến (elastic deformation) và phối cảnh (perspective transform). Các kỹ thuật tăng cường quang học bao gồm thay đổi độ sáng (brightness), độ tương phản (contrast), bão hòa màu (saturation), cân bằng màu (hue shift), thêm nhiễu Gaussian và làm mờ ảnh (blur). Phương pháp Mixup đề xuất bởi Zhang và cộng sự năm 2018 tạo ra ảnh tổng hợp bằng cách nội suy tuyến tính cả ảnh lẫn nhãn của hai mẫu gốc theo công thức $\tilde{x} = \lambda x_i + (1 - \lambda)x_j$ với $\lambda$ lấy mẫu từ phân phối Beta, cải thiện độ chính xác phân loại từ 0.3 đến 2.5 phần trăm trên nhiều benchmark và tăng đáng kể độ bền vững (robustness) trước các ví dụ đối nghịch (adversarial examples) [8]. Tương ứng, nhãn của mẫu tổng hợp cũng được nội suy theo cùng hệ số trộn:

$$\tilde{y} = \lambda\,y_i + (1 - \lambda)\,y_j, \qquad \lambda \sim \mathrm{Beta}(\alpha, \alpha)$$

trong đó $\alpha > 0$ là siêu tham số điều khiển độ mạnh của phép trộn; $\alpha$ càng nhỏ thì $\lambda$ càng gần $0$ hoặc $1$ (trộn nhẹ), $\alpha$ càng lớn thì $\lambda$ càng gần $0.5$ (trộn mạnh). CutMix kết hợp các vùng ảnh từ nhiều ảnh khác nhau trong khi CutOut che khuất một vùng ngẫu nhiên của ảnh, cả hai đều khuyến khích mô hình học phân biệt đặc trưng từ nhiều vùng không gian của ảnh thay vì phụ thuộc quá mức vào một vùng cục bộ.


AutoAugment và các biến thể như RandAugment, TrivialAugment đánh dấu bước chuyển quan trọng từ tăng cường được thiết kế thủ công sang tăng cường được tìm kiếm tự động hoặc ngẫu nhiên hóa có nguyên tắc. AutoAugment sử dụng học tăng cường để tìm kiếm chính sách tăng cường tối ưu trong không gian tổ hợp các phép biến đổi và xác suất áp dụng của chúng, đạt được cải thiện đáng kể trên CIFAR-10, CIFAR-100 và ImageNet so với tăng cường thủ công tốt nhất, nhưng với chi phí tính toán tìm kiếm rất lớn tương đương với huấn luyện năm nghìn mô hình [8]. RandAugment thay thế quá trình tìm kiếm bằng cách chọn ngẫu nhiên từ tập 14 phép biến đổi với cường độ đồng nhất, giữ nguyên hiệu năng của AutoAugment trong khi giảm thiểu đáng kể chi phí tính toán.

Bảng dưới đây phân loại các nhóm kỹ thuật tăng cường dữ liệu cùng tiên nghiệm bất biến mà chúng áp đặt lên mô hình.

| Nhóm kỹ thuật | Ví dụ kỹ thuật | Tiên nghiệm bất biến áp đặt |
|---|---|---|
| Hình học | Lật, xoay, random crop, elastic deformation, perspective | Bất biến với biến đổi không gian (vị trí, hướng, tỉ lệ) |
| Quang học | Brightness, contrast, saturation, hue shift, nhiễu Gaussian, blur | Bất biến với điều kiện chiếu sáng và nhiễu cảm biến |
| Trộn mẫu | Mixup, CutMix, CutOut | Khuyến khích biên quyết định tuyến tính, giảm phụ thuộc vùng cục bộ |
| Tự động hóa | AutoAugment, RandAugment, TrivialAugment | Tối ưu/ngẫu nhiên hóa chính sách tăng cường theo nguyên tắc |

Mặc dù tăng cường dữ liệu là công cụ mạnh mẽ và được áp dụng phổ biến, nó có giới hạn cơ bản không thể vượt qua: mọi biến thể được tạo ra đều phải bắt đầu từ ảnh gốc thực, và kỹ thuật này không thể tạo ra các đối tượng, bối cảnh hay điều kiện hoàn toàn mới không có trong tập dữ liệu gốc, từ đó tạo nên nhu cầu cho các phương pháp sinh dữ liệu ảnh tiên tiến hơn dựa trên mô hình sinh tổng quát [7].


# ỨNG DỤNG VÀ ĐỊNH HƯỚNG PHÁT TRIỂN AI 

## Tối ưu hóa hiệu năng và trí tuệ nhân tạo trên thiết bị biên

Mục này tập trung phân tích một trong những xu hướng kiến trúc quan trọng nhất của ngành trí tuệ nhân tạo hiện đại, đó là sự chuyển dịch từ các mô hình ngôn ngữ lớn truyền thống sang các Small Language Model (Small Language Model) được tối ưu hóa để vận hành trực tiếp trên thiết bị đầu cuối. Quá trình này không chỉ phản ánh nhu cầu thực tiễn về hiệu năng và bảo mật mà còn định hình lại kiến trúc phần mềm của toàn bộ hệ sinh thái ứng dụng trí tuệ nhân tạo trong giai đoạn 2025-2026, khi giới hạn tài nguyên trở thành yếu tố then chốt thay vì chỉ là ràng buộc phụ thuộc.

Small Language Model được định nghĩa là các mô hình ngôn ngữ có quy mô tham số từ năm trăm triệu đến mười lăm tỷ biến số, được thiết kế đặc biệt để chạy tin cậy trên các nền tảng có tài nguyên tính toán hạn chế như thiết bị di động, laptop cá nhân hoặc hệ thống nhúng công nghiệp [13]. Khác với Large Language Model truyền thống thường yêu cầu hàng chục tỷ tham số cùng hạ tầng máy chủ chuyên dụng, Small Language Model duy trì khả năng hiểu và sinh văn bản ở mức chất lượng chấp nhận được thông qua các kỹ thuật nén kiến trúc và huấn luyện thông minh. Lợi ích cốt lõi của việc triển khai trên thiết bị biên bao gồm ba khía cạnh chính: thứ nhất là bảo mật dữ liệu khi mọi xử lý diễn ra cục bộ mà không cần truyền thông tin đến máy chủ từ xa, thứ hai là độ trễ cực thấp với phản hồi chỉ trong vài mili giây nhờ loại bỏ chi phí mạng lưới, và thứ ba là khả năng hoạt động hoàn toàn ngoại tuyến mà không phụ thuộc vào kết nối internet liên tục [13].

Các dòng mô hình Small Language Model tiên tiến nhất năm 2025-2026 đã chứng minh bước tiến vượt bậc về chất lượng, mỗi dòng đều có thế mạnh riêng biệt phục vụ các phân khúc ứng dụng khác nhau. Microsoft Phi Series bao gồm Phi-4-mini với bốn tỷ tham số và phiên bản Phi-4 tiêu chuẩn với sáu tỷ tham số, cả hai đều đạt hiệu suất đáng kinh ngạc trên các bài kiểm tra suy luận logic như GSM8K (General Math Word Problem Solving Knowledge) khi ghi điểm 83 phần trăm. Đây là con số tương đương với một số mô hình tám mươi tỷ tham số của thế hệ trước [13]. Google tiếp tục khẳng định vị thế dẫn đầu thông qua Gemma Series, trong đó Gemma 3 chỉ yêu cầu năm trăm hai mươi chín megabyte bộ nhớ RAM khi chạy phiên bản một tỷ tham số. Đây là một con số chưa từng có trước đây và cho phép tích hợp trực tiếp vào ứng dụng di động không cần hạ tầng bổ trợ. Kiến trúc mô hình này sử dụng cơ chế grouped-query attention (GQA) kết hợp với hàm kích hoạt SwiGLU để tối ưu hóa cả tốc độ suy luận (inference) và chất lượng biểu diễn ngữ nghĩa, đồng thời mở rộng khả năng đa phương thức thông qua Gemma 3n tích hợp sẵn cho thiết bị di động Android với khả năng xử lý văn bản, hình ảnh và âm thanh trong cùng một kiến trúc thống nhất [13]. Alibaba với Qwen Series và Meta với Llama 3.2 cũng cung cấp các lựa chọn mở chất lượng cao, trong đó Qwen 2.5 Mini đạt 78,4 điểm trên benchmark MMLU (Massive Multitask Language Understanding) và vượt xa nhiều mô hình thương mại đóng cùng phân khúc tham số [13]. Những kết quả này khẳng định rằng SLM không còn là giải pháp thay thế giá rẻ mà đã trở thành đối thủ cạnh tranh thực sự trên thị trường. Thị trường SLM cho thấy tốc độ tăng trưởng đáng kể từ mức 0,93 tỷ USD vào năm 2025 dự kiến lên tới 5,45 tỷ USD vào năm 2032 theo báo cáo của Zylos Research, phản ánh nhu cầu ngày càng tăng về giải pháp trí tuệ nhân tạo nhẹ cân (lightweight) trong mọi ngành công nghiệp [13].

Bảng dưới đây tổng hợp các dòng Small Language Model tiêu biểu cùng quy mô tham số, kết quả benchmark nổi bật và yêu cầu tài nguyên.

| Mô hình | Quy mô tham số | Benchmark nổi bật | Yêu cầu bộ nhớ / ghi chú |
|---|---|---|---|
| Microsoft Phi-4-mini / Phi-4 | 4 tỷ / 6 tỷ | GSM8K ≈ 83% | Tương đương mô hình ~80 tỷ thế hệ trước |
| Google Gemma 3 (1B) | 1 tỷ | — | ~529 MB RAM; GQA + SwiGLU |
| Google Gemma 3n | Đa phương thức | Văn bản, ảnh, âm thanh | Tối ưu cho Android |
| Qwen 2.5 Mini | Phân khúc nhỏ | MMLU = 78,4 | Vượt nhiều mô hình đóng cùng phân khúc |
| Meta Llama 3.2 | Mở, nhiều cỡ | — | Lựa chọn mã nguồn mở chất lượng cao |

Benchmark Smol AI WorldCup do HuggingFace tổ chức đã cung cấp một nền tảng đánh giá công bằng và thực tế cho các Small Language Model. Kết quả từ kỳ thi này cho thấy mô hình bốn tỷ tham số có thể đạt được khoảng chín mươi lăm phần trăm chất lượng của mô hình mười bốn tỷ tham số trong khi chỉ tiêu thụ ba mươi sáu phần trăm bộ nhớ RAM, chứng minh rằng việc giảm quy mô không nhất thiết đồng nghĩa với giảm hiệu năng tương ứng. Dữ liệu này củng cố lập luận rằng kiến trúc tối ưu và kỹ thuật huấn luyện thông minh có thể bù đắp đáng kể cho sự thiếu hụt về số lượng tham số.

Để đạt được hiệu suất cao trên thiết bị biên, các nhà nghiên cứu đã phát triển ba nhóm kỹ thuật cốt lõi: Knowledge Distillation (Knowledge Distillation), Quantization (Lượng tử hóa), và Pruning cùng Mixed Precision (Sparsity lựa chọn) [10]. Knowledge Distillation hoạt động theo nguyên lý huấn luyện một mô hình học sinh nhỏ bắt chước hành vi đầu ra của một mô hình thầy lớn hơn. Quá trình này không chỉ sao chép xác suất phân phối lớp mà còn truyền đạt thông tin về cấu trúc latent space, cho phép mô hình nhỏ nắm bắt được quy luật tổng quát thay vì chỉ khớp với nhãn cứng. Hàm mất mát của quá trình chưng cất thường kết hợp thành phần học từ nhãn cứng và thành phần học từ phân phối mềm của mô hình thầy:

$$\mathcal{L}_{\text{KD}} = (1 - \alpha)\,\mathcal{L}_{\text{CE}}\big(y,\, \sigma(z_s)\big) + \alpha\,\tau^{2}\,\mathrm{KL}\!\big(\sigma(z_t/\tau)\,\|\,\sigma(z_s/\tau)\big)$$

trong đó $z_s$ và $z_t$ là logit của mô hình học sinh và mô hình thầy, $\sigma$ là hàm softmax, $\tau$ là nhiệt độ làm mềm phân phối, và $\alpha \in [0,1]$ cân bằng giữa hai thành phần mất mát. Microsoft đã áp dụng thành công phương pháp này để phát triển encoder-decoder SLM, cải thiện hiệu năng từ sáu đến tám phần trăm trên các bài kiểm tra đánh giá suy luận so với phiên bản chưa qua distillation [13]. Một nghiên cứu khác về SLMRec trong lĩnh vực gợi ý sản phẩm cho thấy việc áp dụng Knowledge Distillation giúp giảm kích thước mô hình từ bảy tỷ xuống dưới một tỷ tham số trong khi vẫn duy trì độ chính xác gợi ý, đồng thời tăng tốc quá trình suy luận lên tám lần nhờ giảm đáng kể độ phức tạp tính toán [13].

Quantization hay lượng tử hóa là kỹ thuật chuyển đổi trọng số và kích hoạt từ độ chính xác số học cao như FP16 sang định dạng bit thấp hơn như INT8 hoặc INT4, qua đó giảm đáng kể bộ nhớ cần thiết và tăng tốc độ suy luận. Phép lượng tử hóa đồng nhất (uniform quantization) ánh xạ giá trị thực $x$ về số nguyên qua bước lượng tử $s$:

$$x_q = \mathrm{round}\!\left(\frac{x}{s}\right), \qquad s = \frac{x_{\max} - x_{\min}}{2^{b} - 1}$$

trong đó $b$ là số bit của định dạng đích (ví dụ $b = 8$ cho INT8) và $s$ là kích thước bước lượng tử. Các phương pháp tiên tiến bao gồm GPTQ (Generative Perceptual Quantization) sử dụng thống kê thứ tự thứ hai để phân bố lỗi lượng tử hóa tối ưu, AWQ (Activation-Aware Quantization) điều chỉnh ngưỡng lượng tử hóa dựa trên phân phối kích hoạt để bảo toàn các giá trị quan trọng có ảnh hưởng lớn đến đầu ra, và SmoothQuant san bằng độ lệch giữa phân phối trọng số và kích hoạt trước khi lượng tử hóa. Nghiên cứu SLMQuant được Wang và cộng sự công bố tại ACM RichMediaGAI 2025 đã thực hiện đánh giá toàn diện về hiệu năng lượng tử hóa trên tập hợp ba mươi Small Language Model khác nhau, với kết quả cho thấy kiến trúc lượng tử hóa W8A8 (bát bit cho trọng số và kích hoạt) có thể bảo toàn độ chính xác với độ sụt giảm dưới 0,5 phần trăm so với phiên bản FP16 gốc trong khi giảm bộ nhớ xuống bốn lần [10]. Đặc biệt, phương pháp này duy trì chất lượng đầu ra của mô hình trên các tác vụ đa dạng bao gồm dịch máy, hiểu ngôn ngữ tự nhiên và suy luận toán học mà không bị suy giảm đáng kể.

Pruning hay tỉa mạch loại bỏ các kết nối hoặc neuron ít đóng góp vào đầu ra cuối cùng, từ đó giảm độ phức tạp mô hình mà vẫn giữ nguyên kiến trúc gốc. Quy trình pruning hiện đại sử dụng kỹ thuật iterative magnitude-based pruning, theo đó xóa các kết nối có trọng số nhỏ nhất theo ngưỡng tiến hóa qua nhiều vòng lặp, giúp duy trì 90 phần trăm độ chính xác gốc khi tỉa 30 đến 40 phần trăm tham số mà không cần finetuning lại từ đầu. Khi kết hợp với Mixed Precision, tức là kỹ thuật sử dụng nhiều cấp độ chính xác khác nhau cho từng thành phần của mô hình dựa trên mức độ nhạy cảm của chúng, Pruning có thể đạt được hiệu quả nén vượt trội so với việc áp dụng đơn lẻ. Kiến trúc MoE (Mixture of Experts) cũng đang được nghiên cứu để áp dụng cho Small Language Model, trong đó chỉ một phần tham số được kích hoạt tại mỗi bước suy luận nhờ cơ chế gating thông minh, giúp giảm chi phí tính toán trung bình khi mở rộng quy mô tổng thể [13]. Một phiên bản nhỏ hóa của MoE là Router-based MoE với chỉ hai đến bốn expert thay vì hàng trăm như trong các mô hình gốc, cho phép Small Language Model tiếp cận lợi ích của kiến trúc MoE mà không làm tăng bộ nhớ vượt quá giới hạn thiết bị biên.

Bảng sau đối chiếu ba nhóm kỹ thuật nén mô hình cốt lõi theo nguyên lý hoạt động và hiệu quả điển hình.

| Kỹ thuật | Nguyên lý cốt lõi | Hiệu quả điển hình |
|---|---|---|
| Knowledge Distillation | Mô hình học sinh nhỏ bắt chước phân phối mềm của mô hình thầy | Giảm 7B → <1B, suy luận nhanh 8×; cải thiện 6–8% reasoning |
| Quantization (W8A8) | Chuyển FP16 → INT8/INT4 qua bước lượng tử | Giảm bộ nhớ 4×, sụt độ chính xác <0,5% |
| Pruning + Mixed Precision | Tỉa kết nối/neuron trọng số nhỏ theo vòng lặp | Giữ ~90% độ chính xác khi tỉa 30–40% tham số |

Các công cụ triển khai hiện đại đóng vai trò then chốt trong việc chuyển hóa lý thuyết sang thực tiễn, mỗi nền tảng đều tối ưu hóa cho hệ sinh thái phần cứng đặc thù. Google AI Edge (Google LiteRT) cung cấp bộ công cụ full-stack từ tối ưu hóa mô hình trước khi biên dịch thông qua TensorFlow Lite Converter cho đến suy luận thời gian thực trên chip TPU và ARM Cortex, với hỗ trợ sẵn có cho các hàm tích chập và attention được tối ưu hóa chuyên biệt nhằm đạt tốc độ inference lên đến 120 tokens trên giây trên bộ xử lý điện thoại flagship thế hệ mới nhất. Apple Core ML tạo thành nền tảng chạy mô hình trí tuệ nhân tạo trong hệ sinh thái iOS và macOS, tự động lựa chọn giữa CPU, GPU và Neural Engine tùy thuộc vào đặc tính tác vụ và thiết bị người dùng đang sử dụng. Chẳng hạn như với chip A17 Pro tích hợp 16-core Neural Engine chuyên biệt cho phép Small Language Model chạy với độ trễ dưới hai mươi mili giây. ONNX Runtime đóng vai trò như lớp trừu tượng hóa đa nền tảng cho phép một mô hình đã chuyển đổi sang định dạng Open Neural Network Exchange chạy trên bất kỳ hệ điều hành hoặc phần cứng nào được hỗ trợ, làm giảm đáng kể chi phí tích hợp giữa các môi trường phát triển khác nhau và hỗ trợ cả CPU truyền thống lẫn accelerator chuyên dụng như Intel OpenVINO và Qualcomm SNPE.

Bảng dưới đây tóm tắt các công cụ triển khai Edge AI phổ biến cùng hệ sinh thái mục tiêu và đặc điểm chính.

| Công cụ | Hệ sinh thái mục tiêu | Đặc điểm chính |
|---|---|---|
| Google AI Edge (LiteRT) | TPU, ARM Cortex | Full-stack từ TF Lite Converter; tới ~120 tokens/giây |
| Apple Core ML | iOS, macOS | Tự chọn CPU/GPU/Neural Engine; độ trễ <20 ms (A17 Pro) |
| ONNX Runtime | Đa nền tảng (CPU, accelerator) | Lớp trừu tượng hóa; hỗ trợ Intel OpenVINO, Qualcomm SNPE |

Case study thực tế minh họa rõ nét hiệu quả của Edge AI trong sản xuất ở nhiều lĩnh vực khác nhau. Google đã triển khai Gemma 3n trực tiếp trên thiết bị Android cho dịch vụ dịch thuật nội địa, cho phép người dùng tại các khu vực có kết nối internet không ổn định vẫn nhận được phản hồi dịch chính xác với độ trễ dưới năm mươi mili giây nhờ suy luận hoàn toàn cục bộ mà không cần truyền dữ liệu qua mạng. Điều này đặc biệt quan trọng đối với người dùng di động và cộng đồng vùng sâu vùng xa. Trong lĩnh vực y tế, một bệnh viện tuyến huyện tại vùng sâu đã triển khai hệ thống phân tích ảnh X-quang phổi sử dụng Small Language Model chạy trên máy chủ nội bộ đảm bảo tuân thủ quy định HIPAA về bảo mật thông tin bệnh nhân, tránh mọi rủi ro truyền dữ liệu nhạy cảm ra bên ngoài mạng lưới tổ chức. Kết quả thử nghiệm trong sáu tháng cho thấy độ nhạy phát hiện bất thường đạt 92,3 phần trăm so với đánh giá của bác sĩ chuyên khoa, đồng thời giảm một nửa thời gian chờ đợi kết quả chẩn đoán ban đầu từ tám phút xuống còn bốn phút. Một case study khác tại ngân hàng thương mại lớn đã áp dụng Phi-4-mini trên server nội địa để xử lý phân tích văn bản hợp đồng pháp lý, tự động trích xuất các điều khoản rủi ro và đề xuất phương án xử lý. Kết quả đạt được mức giảm 60 phần trăm thời gian review hợp đồng so với quy trình thủ công truyền thống [13].

Thị trường Small Language Model đang trải qua giai đoạn tăng trưởng nóng với quy mô dự kiến từ mức không phảy ba ba tỷ USD vào năm hai mươi lăm lên năm phảy bốn lăm tỷ USD vào năm hai mươi ba hai, theo báo cáo của Zylos Research [13]. Xu hướng này được thúc đẩy bởi sự tiến hóa của kiến trúc mô hình: Microsoft Research công bố nghiên cứu năm hai nghìn hai trăm năm mươi về kiến trúc Encoder-Decoder cho Small Language Model, trong đó bộ mã hóa trích xuất đặc trưng ngữ nghĩa còn bộ giải mã thực hiện sinh văn bản theo cơ chế cross-attention. Kết quả thử nghiệm cho thấy kiến trúc này đạt hiệu suất tốt hơn từ hai đến bốn phần trăm so với Decoder-only truyền thống trên các tác vụ tổng hợp thông tin đồng thời giảm bốn mươi bảy phần trăm độ trễ suy luận nhờ loại bỏ bước autoregressive lặp [13]. Bên cạnh đó, xu hướng lai ghép đa phương thức ngày càng trở nên phổ biến khi các Small Language Model không chỉ xử lý văn bản thuần túy mà còn tích hợp khả năng hiểu hình ảnh, âm thanh và video trong cùng một mô hình duy nhất.

Thách thức lớn nhất vẫn nằm ở việc cân bằng giữa kích thước mô hình và độ chính xác thực tế, đặc biệt khi đối mặt với các tác vụ đòi hỏi suy luận đa bước phức tạp hoặc khả năng tiếp cận tri thức từ nhiều lĩnh vực khác nhau trong cùng một phản hồi. Khi giảm tham số xuống mức rất thấp, cụ thể dưới năm trăm triệu, Small Language Model thường thể hiện suy giảm đáng kể về khả năng biểu đạt ngữ nghĩa, dẫn đến kết quả kém tin cậy trên các benchmark đánh giá reasoning như ARC-Challenge hay HumanEval. Ngoài ra, việc tối ưu hóa cho phần cứng cụ thể yêu cầu chuyên môn kỹ thuật sâu mà không phải mọi nhà phát triển đều sở hữu, dẫn đến rào cản gia nhập thị trường đối với các tổ chức vừa và nhỏ có ngân sách nghiên cứu hạn chế. Vấn đề thứ ba là sự thiếu hụt dataset huấn luyện đặc thù cho thiết bị biên, bởi các mô hình thường được huấn luyện trên dữ liệu web chung chung mà không phản ánh đúng ngữ cảnh ứng dụng thực tế của người dùng cuối [13]. Trong tương lai gần, hướng nghiên cứu tập trung vào tự động hóa quá trình tối ưu hóa mô hình (AutoML for SLM) và phát triển các kiến trúc mới như Mixture-of-Embedders để tận dụng tối đa tài nguyên hạn chế mà vẫn đạt chất lượng đầu ra cao nhất [13]. Những tiến bộ trong lĩnh vực này sẽ tiếp tục tạo đà cho sự phát triển của RAG trên thiết bị biên, và đây chính là chủ đề sẽ được phân tích chuyên sâu trong mục tiếp theo.

## Retrieval-Augmented Generation, quản lý tri thức và trách nhiệm AI

Mục này khám phá hai khía cạnh bổ sung cho nhau trong hệ sinh thái trí tuệ nhân tạo hiện đại: mặt kỹ thuật của việc tăng cường khả năng sinh văn bản từ cơ sở tri thức bên ngoài thông qua Retrieval-Augmented Generation, và mặt quản trị của việc đảm bảo các hệ thống trí tuệ nhân tạo được vận hành một cách có trách nhiệm và tuân thủ các chuẩn mực đạo đức cũng như quy định pháp lý ngày càng chặt chẽ. Hai lĩnh vực này không chỉ phản ánh nhu cầu thực tiễn về chất lượng đầu ra mà còn thể hiện sự trưởng thành của ngành trong việc xây dựng nền tảng phát triển bền vững, nơi công nghệ tiên tiến đi đôi với sự minh bạch và trách nhiệm giải trình [3].

Retrieval-Augmented Generation hay tăng cường sinh văn bản từ truy xuất đã trở thành một trong những kiến trúc then chốt để giải quyết vấn đề hallucination. Đây là hiện tượng mô hình sinh thông tin sai lệch hoặc hoàn toàn hư cấu, vốn là hạn chế nghiêm trọng nhất của Large Language Model thuần túy, đặc biệt trong các lĩnh vực yêu cầu độ chính xác cao như y tế, pháp lý và tài chính [3]. Cơ chế hoạt động cơ bản bao gồm ba giai đoạn tuần tự: thứ nhất là Retrieval module tiếp nhận truy vấn người dùng và tìm kiếm tài liệu liên quan nhất từ kho tri thức bên ngoài, thường là cơ sở dữ liệu vector chứa các embedding ngữ nghĩa của văn bản đã được phân đoạn (chunking); thứ hai là Context preparation tổng hợp kết quả truy xuất thành ngữ cảnh có cấu trúc, gán trọng số ưu tiên cho từng đoạn dựa trên mức độ phù hợp với truy vấn gốc thông qua cosine similarity; và cuối cùng là Generation module sử dụng mô hình ngôn ngữ kết hợp cả câu hỏi ban đầu lẫn ngữ cảnh được chèn vào để sinh phản hồi có căn cứ tài liệu cụ thể [3]. Độ tương đồng ngữ nghĩa giữa vector truy vấn $\mathbf{q}$ và vector tài liệu $\mathbf{d}$ thường được đo bằng cosine similarity:

$$\mathrm{sim}(\mathbf{q}, \mathbf{d}) = \cos\theta = \frac{\mathbf{q} \cdot \mathbf{d}}{\lVert \mathbf{q} \rVert \, \lVert \mathbf{d} \rVert}$$

với giá trị nằm trong $[-1, 1]$; giá trị càng gần $1$ thể hiện hai đoạn văn bản càng gần nhau về mặt ngữ nghĩa. Sự kết hợp này đảm bảo mỗi khẳng định trong đầu ra đều có thể truy nguyên đến một nguồn tri thức đáng tin cậy, giảm thiểu đáng kể nguy cơ thông tin sai lệch và tăng cường khả năng giải thích (explainability) của phản hồi, qua đó tạo nên hai yếu tố quan trọng đối với ứng dụng trí tuệ nhân tạo trong doanh nghiệp.

Các cải tiến mới nhất của RAG vượt xa mô hình cơ bản ban đầu theo nhiều hướng nghiên cứu song song. Hybrid Retrieval kết hợp hai phương pháp bổ sung cho nhau: BM25 (Binary Independence Model phiên bản 2) dựa trên tần suất xuất hiện từ khóa truyền thống và Vector Search dựa trên độ tương đồng ngữ nghĩa embedding, qua đó cân bằng giữa khớp từ chính xác và hiểu ý nghĩa ngầm ẩn trong truy vấn. Điểm số BM25 của một tài liệu $d$ với truy vấn $q$ được tính theo công thức:

$$\mathrm{BM25}(q, d) = \sum_{t \in q} \mathrm{IDF}(t) \cdot \frac{f(t, d)\,(k_1 + 1)}{f(t, d) + k_1\!\left(1 - b + b\,\dfrac{|d|}{\text{avgdl}}\right)}$$

trong đó $f(t, d)$ là tần suất của từ $t$ trong tài liệu $d$, $|d|$ là độ dài tài liệu, $\text{avgdl}$ là độ dài trung bình của tài liệu trong kho, còn $k_1$ và $b$ là các siêu tham số điều chỉnh độ bão hòa tần suất và mức độ chuẩn hóa độ dài. Nghiên cứu thực nghiệm cho thấy phương pháp này cải thiện Recall@10 lên đến 18 phần trăm so với việc chỉ sử dụng một trong hai kỹ thuật. Knowledge Graph-Enhanced RAG đưa vào thêm lớp thông tin quan hệ thực thể dưới dạng đồ thị tri thức, cho phép hệ thống không chỉ tìm kiếm tài liệu đơn lẻ mà còn suy luận mối liên hệ giữa các khái niệm. Ví dụ khi người dùng hỏi về tác động của biến đổi khí hậu đến ngành nông nghiệp, hệ thống có thể truy xuất cả chuỗi nguyên nhân từ nhiệt độ tăng đến thay đổi mùa vụ đến giảm năng suất cây trồng [3]. Agentic RAG đại diện cho bước tiến tự động hóa cao nhất, trong đó agent AI tự động điều chỉnh chiến lược truy xuất dựa trên phản hồi tức thời: nếu kết quả ban đầu không đủ tin cậy, agent sẽ tìm kiếm thêm tài liệu từ nguồn khác hoặc phân tích đa chiều trước khi sinh câu trả lời cuối cùng. Nghiên cứu so sánh hiệu năng hệ thống RAG/Agent được Liu và cộng sự công bố năm 2025 cho thấy Agentic RAG vượt trội khoảng mười lăm phần trăm về độ chính xác thông tin so với phiên bản cơ bản trên tập dữ liệu đánh giá có cấu trúc phức tạp, đồng thời giảm ba mươi phần trăm số lần truy vấn thừa nhờ cơ chế self-reflection tự động (self-reflection mechanism) [8].

Bảng dưới đây so sánh các biến thể RAG tiêu biểu theo cơ chế chính và mức cải thiện được báo cáo.

| Biến thể RAG | Cơ chế chính | Cải thiện được báo cáo |
|---|---|---|
| RAG cơ bản | Retrieval → Context → Generation | Nền tảng tham chiếu, giảm hallucination |
| Hybrid Retrieval | Kết hợp BM25 (từ khóa) + Vector Search (ngữ nghĩa) | Recall@10 tăng tới 18% |
| Knowledge Graph-Enhanced RAG | Bổ sung lớp quan hệ thực thể dạng đồ thị tri thức | Suy luận chuỗi nguyên nhân đa khái niệm |
| Agentic RAG | Agent tự điều chỉnh chiến lược truy xuất + self-reflection | +15% độ chính xác, −30% truy vấn thừa |

On-device RAG mở rộng khả năng của mô hình ra ngoài môi trường điện toán đám mây, cho phép toàn bộ quá trình truy xuất và sinh văn bản diễn ra cục bộ trên thiết bị người dùng mà không cần kết nối mạng. Google AI Edge đã chứng minh tính khả thi của kiến trúc này thông qua việc tích hợp Vector Search Engine trực tiếp vào nền tảng LiteRT, cho phép thiết bị Android truy vấn cơ sở tri thức nhúng trong bộ nhớ flash với thời gian trả về trung bình dưới hai trăm mili giây. Đây là một đột phá quan trọng cho các ứng dụng doanh nghiệp yêu cầu bảo mật dữ liệu tuyệt đối [3]. Case study thực tế tại NVIDIA cho thấy việc triển khai RAG trong lĩnh vực chăm sóc sức khỏe giúp bác sĩ truy xuất nhanh chóng hồ sơ bệnh án điện tử và tài liệu y văn mới nhất, giảm đáng kể thời gian chẩn đoán trong môi trường khẩn cấp đồng thời đảm bảo tuân thủ các quy định về bảo mật thông tin bệnh nhân HIPAA; hệ thống này xử lý hơn năm nghìn lượt truy vấn hàng ngày với độ chính xác trung bình 94,7 phần trăm so với đánh giá của hội đồng bác sĩ chuyên khoa. Microsoft cũng ứng dụng Graph RAG trong Microsoft Copilot+, cho phép người dùng doanh nghiệp soạn thảo báo cáo tích hợp thông tin từ nhiều nguồn nội bộ khác nhau một cách tự động; kết quả thử nghiệm quy mô toàn cầu cho thấy thời gian soạn báo cáo giảm 70 phần trăm so với phương pháp thủ công truyền thống và tăng bốn mươi hai phần trăm sự hài lòng của nhân viên đối với công cụ hỗ trợ ra quyết định [3].

Trách nhiệm trí tuệ nhân tạo và quản trị (Responsible AI and Governance) đã trở thành yêu cầu bắt buộc khi hệ thống trí tuệ nhân tạo thâm nhập sâu vào mọi khía cạnh đời sống xã hội. Bối cảnh quy định pháp lý toàn cầu đang hình thành nhanh chóng với nhiều khuôn khổ khác nhau phản ánh ưu tiên văn hóa và chính trị của từng khu vực. Liên minh Châu Âu thông qua EU AI Act, tức đạo luật đầu tiên trên thế giới đặt ra khung pháp lý toàn diện cho trí tuệ nhân tạo, và phân loại các ứng dụng theo bốn mức rủi ro: không thể chấp nhận được (như hệ thống chấm điểm xã hội bị cấm hoàn toàn), rủi ro rất cao (áp dụng cho hệ thống tuyển dụng nhân sự và chẩn đoán y tế với yêu cầu kiểm thử độc lập nghiêm ngặt trước khi đưa ra thị trường), rủi ro cao (công nghệ nhận diện cảm xúc và quản lý nguy cơ cần tuân thủ quy định minh bạch thông tin), cùng với nhóm rủi ro tối thiểu hoặc không bị hạn chế. Bảng sau hệ thống hóa bốn mức rủi ro này theo ví dụ ứng dụng và yêu cầu pháp lý tương ứng.

| Mức rủi ro | Ví dụ ứng dụng | Yêu cầu pháp lý |
|---|---|---|
| Không thể chấp nhận | Hệ thống chấm điểm xã hội | Bị cấm hoàn toàn |
| Rủi ro rất cao | Tuyển dụng nhân sự, chẩn đoán y tế | Kiểm thử độc lập nghiêm ngặt trước khi ra thị trường |
| Rủi ro cao | Nhận diện cảm xúc, quản lý nguy cơ | Tuân thủ quy định minh bạch thông tin |
| Rủi ro tối thiểu | Ứng dụng AI thông thường | Không bị hạn chế hoặc hạn chế tối thiểu |

Tại Việt Nam, Luật An ninh mạng và Nghị định 13/2023/NĐ-CP hướng dẫn quản lý hoạt động trí tuệ nhân tạo đang dần hoàn thiện khung pháp lý đặc thù, mặc dù vẫn còn thiếu các hướng dẫn chi tiết về implement kỹ thuật và cơ chế giám sát thực thi [11].

OECD đã ban hành OECD Due Diligence Guidance for Responsible AI với sáu bước thực hiện cụ thể: thứ nhất là thiết lập khung quản trị và xác định trách nhiệm; thứ hai là tích hợp nguyên tắc RAI vào toàn bộ vòng đời phát triển sản phẩm; thứ ba là đánh giá rủi ro tiềm ẩn liên quan đến thiên kiến, bảo mật và tác động xã hội; thứ tư là giảm thiểu rủi ro thông qua kiểm thử, giám sát và điều chỉnh liên tục; thứ năm là thiết lập cơ chế giải trình và báo cáo minh bạch cho bên liên quan; và cuối cùng là xây dựng văn hóa tổ chức tôn trọng các giá trị đạo đức AI [11]. Khung sáu bước này không mang tính ràng buộc pháp lý nhưng đã được hơn một trăm quốc gia thành viên OECD chấp nhận làm nền tảng để phát triển chính sách quốc gia về trí tuệ nhân tạo có trách nhiệm.

Thực tiễn doanh nghiệp cho thấy khoảng cách đáng kể giữa cam kết về trách nhiệm xã hội và năng lực thực thi kỹ thuật thực tế. Khảo sát của BCG và MIT Sloan Management Review năm 2026 chỉ ra rằng tám mươi lăm phần trăm các công ty lớn đã triển khai chương trình Responsible AI ở mức độ nào đó, nhưng chỉ hai mươi lăm phần trăm sở hữu khung trưởng mature với các biện pháp đo lường, giám sát và cải tiến liên tục. Phần còn lại dừng ở mức chính sách bề mặt, thiếu cơ chế thực thi cụ thể [12]. Nguyên nhân chủ yếu xuất phát từ việc nhiều tổ chức chưa đầu tư đúng mức vào hạ tầng kỹ thuật cần thiết cho việc giám sát mô hình, dẫn đến các nguyên tắc RAI chỉ tồn tại trên văn bản mà không đi kèm công cụ đo lường và cảnh báo tự động phù hợp. Xu hướng mới nhất là ưu tiên xây dựng nền tảng kỹ thuật thay vì chỉ ban hành văn bản chính sách: các công ty đang đầu tư vào công cụ tự động phát hiện thiên kiến (bias detection tool), hệ thống giám sát mô hình thời gian thực và quy trình review độc lập trước khi đưa mô hình vào sản xuất. Vai trò mới của Chief AI Governance Officer hay AI Auditor cũng đang dần trở thành vị trí quản trị không thể thiếu tại các tập đoàn công nghệ lớn, chịu trách nhiệm đảm bảo rằng mọi sản phẩm trí tuệ nhân tạo đều đáp ứng tiêu chuẩn đạo đức và pháp lý trước khi ra mắt thị trường [12].

Hallucination vẫn là thách thức tồn đọng mặc dù RAG đã giảm đáng kể tần suất xuất hiện, với mức giảm ước tính khoảng tám mươi phần trăm so với mô hình thuần túy sinh văn bản không tham chiếu. Các nghiên cứu mới tập trung vào việc phát triển self-verification mechanism cho phép mô hình tự kiểm tra độ tin cậy của thông tin trước khi trình bày đến người dùng cuối, trong đó cơ chế phản hồi tự động (self-reflection) được áp dụng để so sánh các trích dẫn từ retrieval với nội dung đã sinh ra và đánh giá tính nhất quán logic [6]. Kỹ thuật này đặc biệt hiệu quả với Agentic RAG vì agent có thể thực hiện nhiều vòng tự kiểm tra liên tiếp, trong đó mỗi vòng tinh chỉnh độ chính xác thông tin thêm năm đến bảy phần trăm cho đến khi đạt ngưỡng tin cậy mục tiêu. Xu hướng Self-hosted AI deployment cũng ngày càng phổ biến khi doanh nghiệp muốn kiểm soát hoàn toàn dữ liệu đầu vào và đầu ra mà không phụ thuộc vào nhà cung cấp đám mây, đặc biệt trong các ngành có yêu cầu tuân thủ nghiêm ngặt như tài chính ngân hàng và quốc phòng. Các công cụ tự động hóa Governance như framework HEAT (Human Oversight, Evaluation, Accountability, Transparency) đang giúp tổ chức quản lý vòng đời mô hình trí tuệ nhân tạo một cách hệ thống từ giai đoạn thiết kế cho đến khi đưa vào vận hành thực tế, với khả năng phát hiện tự động các rủi ro về thiên kiến và đề xuất biện pháp giảm thiểu tương ứng [12].

Tương lai của RAG hướng đến sự tích hợp sâu hơn với các thành phần AI agent, nơi quá trình truy xuất tri thức không còn là bước thụ động mà được chủ động lập kế hoạch và tối ưu hóa động dựa trên ngữ cảnh nhiệm vụ cụ thể. Hướng nghiên cứu Hybrid Agentic-RAG kết hợp khả năng suy luận đa bước của agent với độ chính xác truy xuất thông tin của RAG đang thu hút sự quan tâm đáng kể từ cộng đồng học thuật và doanh nghiệp, hứa hẹn mở ra khả năng xử lý các câu hỏi phức tạp liên ngành mà không một phương pháp đơn lẻ nào có thể đáp ứng hiệu quả [8]. Đồng thời, xu hướng federated learning kết hợp với on-device RAG sẽ cho phép tổ chức cải thiện mô hình từ dữ liệu người dùng phân tán mà không cần tập trung về máy chủ trung tâm, qua đó vừa nâng cao chất lượng dịch vụ vừa đảm bảo quyền riêng tư dữ liệu cá nhân [3]. Bên cạnh đó, sự phát triển của Multi-modal RAG cho phép truy xuất và kết hợp cả văn bản, hình ảnh, âm thanh và video trong cùng một ngữ cảnh sinh văn bản đang mở rộng đáng kể phạm vi ứng dụng của kiến trúc này ra ngoài các tác vụ xử lý ngôn ngữ thuần túy. Những tiến bộ này đặt nền móng cho các hệ thống trí tuệ nhân tạo thế hệ mới, vốn thông minh hơn, tin cậy hơn và đáng tin cậy trong việc bảo vệ quyền lợi của người dùng và tổ chức, từ đó củng cố niềm tin xã hội vào sự phát triển không ngừng của công nghệ AI. Sự kết hợp hài hòa giữa Edge AI và RAG có trách nhiệm sẽ định hình lại cách doanh nghiệp và cá nhân tương tác với trí tuệ nhân tạo trong những năm tới, khi hiệu suất cao đi đôi với minh bạch và an toàn.


# TÀI LIỆU THAM KHẢO {-}

[1] Krizhevsky, A., Sutskever, I., & Hinton, G. E. (2012). ImageNet Classification with Deep Convolutional Neural Networks. In Advances in Neural Information Processing Systems 25 (NeurIPS 2012).

[2] Zhai, X., Kolesnikov, A., Houlsby, N., & Beyer, L. (2022). Scaling Vision Transformers. In Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR 2022).

[3] Lin, T.-Y., Goyal, P., Girshick, R., He, K., & Dollar, P. (2017). Focal Loss for Dense Object Detection. In Proceedings of the IEEE International Conference on Computer Vision (ICCV 2017).

[4] Ganin, Y., & Lempitsky, V. (2015). Unsupervised Domain Adaptation by Backpropagation. In Proceedings of the 32nd International Conference on Machine Learning (ICML 2015).

[5] Esteva, A., Kuprel, B., Novoa, R. A., Ko, J., Swetter, S. M., Blau, H. M., & Thrun, S. (2017). Dermatologist-level classification of skin cancer with deep neural networks. Nature, 542, 115-118.

[6] Bergmann, P., Fauser, M., Sattlegger, D., & Steger, C. (2019). MVTec AD: A Comprehensive Real-World Dataset for Unsupervised Anomaly Detection. In Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR 2019).

[7] Cordts, M., Omran, M., Ramos, S., Rehfeld, T., Enzweiler, M., Benenson, R., Franke, U., Roth, S., & Schiele, B. (2016). The Cityscapes Dataset for Semantic Urban Scene Understanding. In Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition (CVPR 2016).

[8] Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., Kuttler, H., Lewis, M., Yih, W.-t., Rocktaschel, T., Riedel, S., & Kiela, D. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. In Advances in Neural Information Processing Systems 33 (NeurIPS 2020).

[9] Zhang, H., Cisse, M., Dauphin, Y. N., & Lopez-Paz, D. (2018). mixup: Beyond Empirical Risk Minimization. In International Conference on Learning Representations (ICLR 2018).

[10] Wang, H., et al. (2025). SLMQuant: Quantization for Small Language Models. In ACM RichMediaGAI 2025.

[11] OECD. (2024). OECD Due Diligence Guidance for Responsible AI. OECD Publishing.

[12] Boston Consulting Group & MIT Sloan Management Review. (2026). The State of Responsible AI in the Enterprise.

[13] Zylos Research. (2025). Small Language Model Market Forecast 2025-2032.